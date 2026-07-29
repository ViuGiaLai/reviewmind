from __future__ import annotations

from fastapi import HTTPException, UploadFile


async def read_upload_limited(
    file: UploadFile,
    *,
    max_bytes: int,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    """Read an upload with an early hard limit instead of one unbounded read."""
    content = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        if len(content) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.",
            )
        content.extend(chunk)
    return bytes(content)
