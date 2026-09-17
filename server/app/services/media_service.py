"""Private user-media validation, persistence and short-lived access.

Development and tests use a private local directory. A fixed-disk self-hosted
deployment may explicitly use an absolute persistent local directory;
container platforms use either a private Tencent COS bucket or the CloudBase
PG Storage HTTP API. Database rows store opaque references; callers only
receive application URLs protected by a short-lived HMAC. The application
proxies bounded object bytes after checking that HMAC, so the mini program
never needs a public bucket or a storage credential.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import shutil
import time
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import UploadFile
import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from qcloud_cos import CosClientError, CosConfig, CosS3Client, CosServiceError
except ImportError:
    # Self-hosted deployments use local_persistent storage and intentionally
    # omit the Tencent COS SDK (and its native crcmod build dependency).
    CosConfig = None
    CosS3Client = None

    class CosClientError(Exception):
        pass

    class CosServiceError(Exception):
        pass

from app.config import settings
from app.core.errors import BusinessError


MediaKind = Literal["avatar", "chat"]

_SAFE_FILENAME = re.compile(r"^[0-9a-f]{64}\.jpg$")
_LEGACY_AVATAR_FILENAME = re.compile(r"^[0-9]+-[0-9a-f]{32}\.jpg$")
_AVATAR_REFERENCE = re.compile(r"^media:avatar:([0-9a-f]{64}\.jpg)$")
_CHAT_REFERENCE = re.compile(r"^media:chat:([1-9][0-9]*):([0-9a-f]{64}\.jpg)$")
_LEGACY_AVATAR_REFERENCE = re.compile(r"^/uploads/avatars/([0-9]+-[0-9a-f]{32}\.jpg)$")
_ALLOWED_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}


class MediaStorageError(RuntimeError):
    """The private backing store could not complete an operation."""


@dataclass(frozen=True)
class StoredMedia:
    reference: str
    size: int
    path: Optional[Path] = None
    object_key: Optional[str] = None


def _uses_cos() -> bool:
    return settings.media_storage_backend == "cos"


def _uses_cloudbase_pg() -> bool:
    return settings.media_storage_backend == "cloudbase_pg"


def _uses_remote_storage() -> bool:
    return _uses_cos() or _uses_cloudbase_pg()


def media_root() -> Path:
    """Return the canonical private root for either local storage mode."""
    configured = Path(settings.media_storage_dir).expanduser()
    if (
        settings.media_storage_backend == "local_persistent"
        and not configured.is_absolute()
    ):
        # Settings rejects this at startup. Keep the storage boundary intact if
        # configuration is replaced or monkeypatched after validation.
        raise MediaStorageError("持久化媒体目录必须使用绝对路径")
    root = configured.resolve()
    if settings.media_storage_backend == "local_persistent" and root == Path(root.anchor):
        raise MediaStorageError("持久化媒体目录不能使用文件系统根目录")
    return root


def _make_private_directory(directory: Path, *, parents: bool = False) -> None:
    directory.mkdir(parents=parents, exist_ok=True, mode=0o700)
    try:
        directory.chmod(0o700)
    except OSError:
        # Windows permissions are applied to the service directory ACL during
        # deployment; chmod remains useful on POSIX self-hosted installations.
        pass


def ensure_media_directories() -> None:
    """Prepare private local storage; remote backends create no local media dirs."""
    if _uses_remote_storage():
        return
    root = media_root()
    _make_private_directory(root, parents=True)
    _make_private_directory(root / "avatar")
    _make_private_directory(root / "chat")


def _safe_child(*parts: str) -> Path:
    root = media_root()
    candidate = root.joinpath(*parts).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("invalid media path")
    return candidate


@lru_cache(maxsize=4)
def _configured_cos_client(
    secret_id: str,
    secret_key: str,
    region: str,
    token: str,
) -> CosS3Client:
    if CosConfig is None or CosS3Client is None:
        raise MediaStorageError("COS 存储后端未安装腾讯云 SDK")
    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token or None,
        Scheme="https",
    )
    return CosS3Client(config)


def _cos_client() -> CosS3Client:
    return _configured_cos_client(
        settings.media_cos_secret_id,
        settings.media_cos_secret_key,
        settings.media_cos_region,
        settings.media_cos_token,
    )


def _cloudbase_request(method: str, path: str, **kwargs) -> httpx.Response:
    """Call the PG Storage API with an environment-scoped service-role key."""
    env_id = settings.media_cloudbase_env_id.strip()
    api_key = settings.media_cloudbase_api_key.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,127}", env_id) or not api_key:
        raise MediaStorageError("CloudBase 云存储配置不完整")
    request_headers = {
        "Authorization": f"Bearer {api_key}",
        **kwargs.pop("headers", {}),
    }
    try:
        with httpx.Client(
            base_url=f"https://{env_id}.api.tcloudbasegateway.com",
            headers=request_headers,
            timeout=settings.media_cloudbase_timeout_seconds,
            follow_redirects=False,
        ) as client:
            return client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise MediaStorageError("CloudBase 云存储请求失败") from exc


def _cloudbase_bucket_path() -> str:
    bucket = settings.media_cloudbase_bucket.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", bucket):
        raise MediaStorageError("CloudBase 云存储 Bucket 配置无效")
    return quote(bucket, safe="")


def _cloudbase_object_path(key: str) -> str:
    encoded_key = "/".join(quote(part, safe="") for part in key.split("/"))
    return f"/v1/storages/object/{_cloudbase_bucket_path()}/{encoded_key}"


def _cos_key(kind: MediaKind, filename: str, assignment_id: Optional[int] = None) -> str:
    if not _SAFE_FILENAME.fullmatch(filename):
        raise ValueError("invalid media filename")
    prefix = settings.media_cos_prefix.strip("/")
    if kind == "avatar":
        return f"{prefix}/avatar/{filename}"
    if assignment_id is None or assignment_id < 1:
        raise ValueError("invalid assignment id")
    return f"{prefix}/chat/{assignment_id}/{filename}"


async def read_normalized_image(
    upload: UploadFile,
    *,
    max_bytes: int,
    crop_square: bool = False,
) -> bytes:
    """Read a bounded upload, decode it with Pillow, and return metadata-free JPEG."""
    try:
        raw = await upload.read(max_bytes + 1)
    finally:
        await upload.close()

    if not raw:
        raise BusinessError("INVALID_IMAGE", "请选择一张图片")
    if len(raw) > max_bytes:
        raise BusinessError("IMAGE_TOO_LARGE", f"图片不能超过 {max_bytes // (1024 * 1024)} MB")

    try:
        with Image.open(BytesIO(raw)) as probe:
            source_format = probe.format
            width, height = probe.size
            frames = getattr(probe, "n_frames", 1)
            if source_format not in _ALLOWED_SOURCE_FORMATS or frames != 1:
                raise BusinessError("INVALID_IMAGE", "仅支持静态 JPG、PNG 或 WEBP 图片")
            if (
                width < 1
                or height < 1
                or width > 12000
                or height > 12000
                or width * height > settings.media_max_pixels
            ):
                raise BusinessError("INVALID_IMAGE", "图片尺寸过大，请换一张")
            probe.verify()

        with Image.open(BytesIO(raw)) as decoded:
            decoded.load()
            image = ImageOps.exif_transpose(decoded)
            if crop_square:
                image = ImageOps.fit(image, (512, 512), method=Image.Resampling.LANCZOS)
            else:
                image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)

            # Re-encoding strips EXIF and other source metadata. Transparency is
            # flattened to a deterministic white background.
            output = Image.new("RGB", image.size, "#ffffff")
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                output.paste(rgba, mask=rgba.getchannel("A"))
            else:
                output.paste(image.convert("RGB"))

        encoded = BytesIO()
        output.save(encoded, format="JPEG", quality=86, optimize=True)
        normalized = encoded.getvalue()
        if not normalized or len(normalized) > max_bytes:
            raise BusinessError("IMAGE_TOO_LARGE", "图片处理后仍然过大，请换一张")
        return normalized
    except BusinessError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise BusinessError("INVALID_IMAGE", "图片无法识别，请重新选择") from None


def _write_private_image(data: bytes, directory: Path) -> tuple[str, Path]:
    _make_private_directory(directory, parents=True)
    filename = f"{secrets.token_hex(32)}.jpg"
    destination = directory / filename
    temporary = directory / f".{filename}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    return filename, destination


def _store_cos_image(data: bytes, kind: MediaKind, assignment_id: Optional[int]) -> StoredMedia:
    filename = f"{secrets.token_hex(32)}.jpg"
    key = _cos_key(kind, filename, assignment_id)
    try:
        _cos_client().put_object(
            Bucket=settings.media_cos_bucket,
            Key=key,
            Body=data,
            EnableMD5=True,
            ContentType="image/jpeg",
            CacheControl="private, max-age=300",
            ContentDisposition="inline",
        )
    except (CosClientError, CosServiceError, OSError) as exc:
        raise MediaStorageError("COS 图片写入失败") from exc
    reference = (
        f"media:avatar:{filename}"
        if kind == "avatar"
        else f"media:chat:{assignment_id}:{filename}"
    )
    return StoredMedia(reference=reference, size=len(data), object_key=key)


def _store_cloudbase_image(
    data: bytes,
    kind: MediaKind,
    assignment_id: Optional[int],
) -> StoredMedia:
    filename = f"{secrets.token_hex(32)}.jpg"
    key = _cos_key(kind, filename, assignment_id)
    response = _cloudbase_request(
        "POST",
        _cloudbase_object_path(key),
        content=data,
        headers={"Content-Type": "image/jpeg", "x-upsert": "false"},
    )
    if response.status_code != 200:
        raise MediaStorageError("CloudBase 图片写入失败")
    reference = (
        f"media:avatar:{filename}"
        if kind == "avatar"
        else f"media:chat:{assignment_id}:{filename}"
    )
    return StoredMedia(reference=reference, size=len(data), object_key=key)


def store_avatar(data: bytes) -> StoredMedia:
    if _uses_cloudbase_pg():
        return _store_cloudbase_image(data, "avatar", None)
    if _uses_cos():
        return _store_cos_image(data, "avatar", None)
    filename, path = _write_private_image(data, _safe_child("avatar"))
    return StoredMedia(reference=f"media:avatar:{filename}", path=path, size=len(data))


def store_chat_image(data: bytes, assignment_id: int) -> StoredMedia:
    if assignment_id < 1:
        raise ValueError("invalid assignment id")
    if _uses_cloudbase_pg():
        return _store_cloudbase_image(data, "chat", assignment_id)
    if _uses_cos():
        return _store_cos_image(data, "chat", assignment_id)
    filename, path = _write_private_image(data, _safe_child("chat", str(assignment_id)))
    return StoredMedia(
        reference=f"media:chat:{assignment_id}:{filename}",
        path=path,
        size=len(data),
    )


def parse_reference(reference: Optional[str]) -> Optional[tuple[MediaKind, Optional[int], str]]:
    if not reference:
        return None
    avatar = _AVATAR_REFERENCE.fullmatch(reference)
    if avatar:
        return "avatar", None, avatar.group(1)
    chat = _CHAT_REFERENCE.fullmatch(reference)
    if chat:
        return "chat", int(chat.group(1)), chat.group(2)
    legacy = _LEGACY_AVATAR_REFERENCE.fullmatch(reference)
    if legacy:
        return "avatar", None, legacy.group(1)
    return None


def reference_belongs_to_chat(reference: Optional[str], assignment_id: int) -> bool:
    parsed = parse_reference(reference)
    return bool(parsed and parsed[0] == "chat" and parsed[1] == assignment_id)


def media_path_for_reference(reference: Optional[str]) -> Optional[Path]:
    """Resolve local media only; COS objects never map to a container path."""
    if _uses_remote_storage():
        return None
    parsed = parse_reference(reference)
    if not parsed:
        return None
    kind, assignment_id, filename = parsed
    if kind == "chat":
        return _safe_child("chat", str(assignment_id), filename)

    current = _safe_child("avatar", filename)
    if current.is_file() or _SAFE_FILENAME.fullmatch(filename):
        return current
    if _LEGACY_AVATAR_FILENAME.fullmatch(filename):
        return _safe_child("avatars", filename)
    return None


def _cos_missing(exc: CosServiceError) -> bool:
    try:
        status = int(exc.get_status_code())
    except (TypeError, ValueError):
        status = 0
    try:
        code = str(exc.get_error_code() or "")
    except Exception:
        code = ""
    return status == 404 or code in {"NoSuchKey", "NoSuchObject"}


def delete_managed_media(reference: Optional[str]) -> None:
    parsed = parse_reference(reference)
    if not parsed:
        return
    kind, assignment_id, filename = parsed
    if _uses_cloudbase_pg():
        # Legacy /uploads references were never remote objects.
        if not _SAFE_FILENAME.fullmatch(filename):
            return
        response = _cloudbase_request(
            "DELETE",
            _cloudbase_object_path(_cos_key(kind, filename, assignment_id)),
        )
        if response.status_code not in {200, 404}:
            raise MediaStorageError("CloudBase 图片删除失败")
        return
    if _uses_cos():
        # Legacy /uploads references were never COS objects.
        if not _SAFE_FILENAME.fullmatch(filename):
            return
        try:
            _cos_client().delete_object(
                Bucket=settings.media_cos_bucket,
                Key=_cos_key(kind, filename, assignment_id),
            )
        except CosServiceError as exc:
            if not _cos_missing(exc):
                raise MediaStorageError("COS 图片删除失败") from exc
        except (CosClientError, OSError) as exc:
            raise MediaStorageError("COS 图片删除失败") from exc
        return
    path = media_path_for_reference(reference)
    if path:
        path.unlink(missing_ok=True)


def delete_chat_assignment_media(assignment_id: int) -> None:
    """Remove all private images for one deleted conversation."""
    if assignment_id < 1:
        return
    if not _uses_remote_storage():
        directory = _safe_child("chat", str(assignment_id))
        if directory.is_dir():
            shutil.rmtree(directory)
        return

    prefix = f"{settings.media_cos_prefix.strip('/')}/chat/{assignment_id}/"
    if _uses_cloudbase_pg():
        cursor = ""
        while True:
            payload: dict[str, object] = {"prefix": prefix, "limit": 1000}
            if cursor:
                payload["cursor"] = cursor
            listed = _cloudbase_request(
                "POST",
                f"/v1/storages/object/list/{_cloudbase_bucket_path()}",
                json=payload,
            )
            if listed.status_code != 200:
                raise MediaStorageError("CloudBase 会话图片列举失败")
            try:
                result = listed.json()
            except ValueError as exc:
                raise MediaStorageError("CloudBase 会话图片列举结果无效") from exc
            if not isinstance(result, dict):
                raise MediaStorageError("CloudBase 会话图片列举结果无效")
            keys: list[str] = []
            for item in result.get("objects") or []:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or item.get("name") or "")
                if key.startswith(prefix):
                    keys.append(key)
            for start in range(0, len(keys), 100):
                deleted = _cloudbase_request(
                    "DELETE",
                    f"/v1/storages/object/{_cloudbase_bucket_path()}",
                    json={"prefixes": keys[start:start + 100]},
                )
                if deleted.status_code != 200:
                    raise MediaStorageError("CloudBase 会话图片清理失败")
            if not result.get("hasNext"):
                break
            next_cursor = str(result.get("nextCursor") or "")
            if not next_cursor or next_cursor == cursor:
                raise MediaStorageError("CloudBase 会话图片列举结果缺少分页游标")
            cursor = next_cursor
        return

    marker = ""
    try:
        while True:
            client = _cos_client()
            result = client.list_objects(
                Bucket=settings.media_cos_bucket,
                Prefix=prefix,
                Marker=marker,
                MaxKeys=1000,
            )
            contents = result.get("Contents") or []
            if isinstance(contents, dict):
                contents = [contents]
            for item in contents:
                key = str(item.get("Key") or "")
                if key.startswith(prefix):
                    client.delete_object(Bucket=settings.media_cos_bucket, Key=key)
            truncated = str(result.get("IsTruncated", "false")).lower() == "true"
            if not truncated:
                break
            next_marker = str(result.get("NextMarker") or "")
            if not next_marker or next_marker == marker:
                raise MediaStorageError("COS 列举结果缺少分页游标")
            marker = next_marker
    except MediaStorageError:
        raise
    except (CosClientError, CosServiceError, OSError) as exc:
        raise MediaStorageError("COS 会话图片清理失败") from exc


def _relative_access_path(kind: MediaKind, assignment_id: Optional[int], filename: str) -> str:
    if kind == "avatar":
        return f"avatar/{filename}"
    return f"chat/{assignment_id}/{filename}"


def _signature(relative_path: str, expires: int) -> str:
    payload = f"media-v1\n{relative_path}\n{expires}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def signed_media_url(reference: Optional[str], *, now: Optional[int] = None) -> Optional[str]:
    """Convert a managed reference into a short-lived relative API URL."""
    if not reference:
        return reference
    parsed = parse_reference(reference)
    if not parsed:
        return reference
    kind, assignment_id, filename = parsed
    relative = _relative_access_path(kind, assignment_id, filename)
    current = int(now if now is not None else time.time())
    bucket = max(1, min(300, settings.media_url_ttl_seconds // 2))
    expires = current - (current % bucket) + settings.media_url_ttl_seconds
    signature = _signature(relative, expires)
    return f"/api/v1/media/{relative}?expires={expires}&sig={signature}"


def verify_signed_request(relative_path: str, expires: int, signature: str, *, now: Optional[int] = None) -> bool:
    current = int(now if now is not None else time.time())
    if expires <= current or expires > current + settings.media_url_ttl_seconds + 30:
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", signature or ""):
        return False
    return hmac.compare_digest(signature, _signature(relative_path, expires))


def media_path_for_request(
    kind: MediaKind,
    filename: str,
    assignment_id: Optional[int] = None,
) -> Optional[Path]:
    if _uses_remote_storage():
        return None
    if kind == "chat":
        if assignment_id is None or assignment_id < 1 or not _SAFE_FILENAME.fullmatch(filename):
            return None
        return _safe_child("chat", str(assignment_id), filename)
    if _SAFE_FILENAME.fullmatch(filename):
        return _safe_child("avatar", filename)
    if _LEGACY_AVATAR_FILENAME.fullmatch(filename):
        return _safe_child("avatars", filename)
    return None


def media_bytes_for_request(
    kind: MediaKind,
    filename: str,
    assignment_id: Optional[int] = None,
) -> Optional[bytes]:
    """Read a bounded local or remote object after the API signature is checked."""
    if not _uses_remote_storage():
        path = media_path_for_request(kind, filename, assignment_id)
        if not path or not path.is_file():
            return None
        limit = max(settings.avatar_max_bytes, settings.chat_image_max_bytes) + 1
        try:
            with path.open("rb") as stream:
                data = stream.read(limit)
        except OSError as exc:
            raise MediaStorageError("本地图片读取失败") from exc
        if len(data) >= limit:
            raise MediaStorageError("本地图片大小超出服务端限制")
        return data

    if not _SAFE_FILENAME.fullmatch(filename):
        return None
    key = _cos_key(kind, filename, assignment_id)
    if _uses_cloudbase_pg():
        response = _cloudbase_request("GET", _cloudbase_object_path(key))
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise MediaStorageError("CloudBase 图片读取失败")
        data = response.content
        limit = max(settings.avatar_max_bytes, settings.chat_image_max_bytes) + 1
        if len(data) >= limit:
            raise MediaStorageError("CloudBase 图片大小超出服务端限制")
        return data
    try:
        response = _cos_client().get_object(Bucket=settings.media_cos_bucket, Key=key)
        stream = response["Body"].get_raw_stream()
        limit = max(settings.avatar_max_bytes, settings.chat_image_max_bytes) + 1
        try:
            data = stream.read(limit)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        if len(data) >= limit:
            raise MediaStorageError("COS 图片大小超出服务端限制")
        return data
    except CosServiceError as exc:
        if _cos_missing(exc):
            return None
        raise MediaStorageError("COS 图片读取失败") from exc
    except MediaStorageError:
        raise
    except (CosClientError, KeyError, OSError) as exc:
        raise MediaStorageError("COS 图片读取失败") from exc
