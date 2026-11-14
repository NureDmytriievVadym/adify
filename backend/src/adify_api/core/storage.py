import asyncio
import re
import uuid
from pathlib import Path

from adify_api.core.config import get_settings

# The first bytes decide the type; the client's Content-Type and file name are not trusted.
SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
]
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def sniff_content_type(data: bytes) -> str | None:
    for prefix, content_type in SIGNATURES:
        if data.startswith(prefix):
            return content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def looks_like_text(data: bytes) -> bool:
    """A conservative text check used to label otherwise unknown evidence files."""
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def clean_filename(filename: str) -> str:
    """Keep only the base name and drop control characters; cap at the DB column size."""
    name = CONTROL_CHARACTERS.sub("", filename.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return name[-255:] or "attachment"


def path_of(attachment_id: uuid.UUID) -> Path:
    return Path(get_settings().storage_dir) / str(attachment_id)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


async def save(attachment_id: uuid.UUID, data: bytes) -> None:
    await asyncio.to_thread(_write, path_of(attachment_id), data)


async def remove(attachment_id: uuid.UUID) -> None:
    await asyncio.to_thread(path_of(attachment_id).unlink, True)
