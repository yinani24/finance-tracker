from __future__ import annotations

import os
import re
import uuid

from app.config import settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(filename: str) -> str:
    """Reduce an uploaded filename to a safe basename.

    Strips any directory components and replaces unusual characters so a
    malicious ``../`` or absolute path in the client-supplied name can never
    escape the storage directory.
    """
    base = os.path.basename(filename or "").strip() or "upload"
    return _SAFE_NAME.sub("_", base)[:200]


def save_upload(content: bytes, filename: str) -> str:
    """Persist raw upload bytes and return an opaque storage key.

    The key is a directory-relative path under ``FT_IMPORT_STORAGE_DIR``. The
    interface is deliberately narrow (bytes in, key out) so a later slice can
    swap the local-disk backend for S3 / Supabase Storage without touching
    callers.
    """
    storage_dir = settings.import_storage_dir
    os.makedirs(storage_dir, exist_ok=True)
    key = f"{uuid.uuid4().hex}_{_sanitize(filename)}"
    path = os.path.join(storage_dir, key)
    with open(path, "wb") as fh:
        fh.write(content)
    return key
