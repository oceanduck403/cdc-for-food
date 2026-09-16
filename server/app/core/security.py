"""JWT / 密码哈希 / 依赖"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import PyJWTError as JWTError
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/wechat", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def admin_auth_fingerprint(user: User) -> str:
    """JWT 中的管理员凭证标记；不向客户端泄露密码哈希。"""
    material = f"{user.id}:{user.token_version}:{user.username}:{user.password_hash}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


def verify_admin_session(payload: dict, user: User) -> None:
    """账号或密码一旦变更，旧 JWT 的凭证标记立即失配。"""
    marker = payload.get("admin_auth")
    if not user.password_hash or not isinstance(marker, str) or not hmac.compare_digest(
        marker, admin_auth_fingerprint(user)
    ):
        raise HTTPException(status_code=401, detail="账号信息已变更，请重新登录")


def create_access_token(subject: str, extra: Optional[dict] = None, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(tz=timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_subject(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token payload")
    try:
        uid = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="invalid token payload")
    user = await db.get(User, uid)
    if not user:
        # A signed token must stop working immediately after its account is
        # deleted; otherwise endpoints that only consume ``sub`` could still run.
        raise HTTPException(status_code=401, detail="账号不存在或已注销")
    if not user.is_active:
        # Disabling a managed account is also a session-revocation operation.
        # Enforce it here so endpoints using only ``current_user_id`` cannot be
        # reached with a token issued before the account was disabled.
        raise HTTPException(status_code=401, detail="账号已停用，请重新登录")
    if user.role == "admin":
        verify_admin_session(payload, user)
    return sub
