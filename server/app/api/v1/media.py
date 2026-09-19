"""Short-lived proxy endpoints for private user-uploaded images."""
import asyncio

from fastapi import APIRouter, HTTPException, Query, Response
from loguru import logger

from app.services.media_service import (
    MediaKind,
    MediaStorageError,
    media_bytes_for_request,
    verify_signed_request,
)


router = APIRouter()
clinical_router = APIRouter()


async def _serve(
    kind: MediaKind,
    filename: str,
    relative_path: str,
    expires: int,
    sig: str,
    assignment_id: int | None = None,
) -> Response:
    # Check the bearer signature before touching storage, so unsigned callers
    # cannot enumerate either local files or private COS object keys.
    if not verify_signed_request(relative_path, expires, sig):
        raise HTTPException(status_code=403, detail="图片访问链接无效或已过期")
    try:
        data = await asyncio.to_thread(
            media_bytes_for_request,
            kind,
            filename,
            assignment_id,
        )
    except MediaStorageError:
        logger.exception("private media read failed: kind={kind}", kind=kind)
        raise HTTPException(status_code=503, detail="图片暂时无法读取，请稍后重试") from None
    if data is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/avatar/{filename}", include_in_schema=False)
async def avatar_image(
    filename: str,
    expires: int = Query(...),
    sig: str = Query(...),
) -> Response:
    relative = f"avatar/{filename}"
    return await _serve("avatar", filename, relative, expires, sig)


@clinical_router.get("/chat/{assignment_id}/{filename}", include_in_schema=False)
async def chat_image(
    assignment_id: int,
    filename: str,
    expires: int = Query(...),
    sig: str = Query(...),
) -> Response:
    relative = f"chat/{assignment_id}/{filename}"
    return await _serve(
        "chat",
        filename,
        relative,
        expires,
        sig,
        assignment_id,
    )
