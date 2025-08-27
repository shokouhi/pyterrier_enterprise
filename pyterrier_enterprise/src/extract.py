from pathlib import Path
from datetime import datetime
from typing import Iterator, Dict, Optional
import os

from tika import parser as tika_parser  # downloads/starts Tika server on first use

# File types we’ll attempt to parse
ALLOWED_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf",
    ".html", ".htm"
}

def safe_read_bytes(path: Path, max_bytes: int) -> Optional[bytes]:
    try:
        if max_bytes and path.stat().st_size > max_bytes:
            return None
        with open(path, "rb") as fh:
            return fh.read()
    except Exception:
        return None

def parse_file(path: Path, max_bytes: int) -> dict:
    """Return {content, metadata} using Tika; empty content on failure."""
    raw = safe_read_bytes(path, max_bytes)
    if raw is None:
        return {"content": "", "metadata": {"X-Parser-Note": "Skipped (size limit)"}}
    try:
        # tika_parser.from_buffer avoids path/URI issues on Windows
        out = tika_parser.from_buffer(raw)
        content = (out.get("content") or "").strip()
        meta = out.get("metadata") or {}
        return {"content": content, "metadata": meta}
    except Exception as e:
        return {"content": "", "metadata": {"X-Parser-Error": str(e)}}

def iter_docs(root: Path, max_bytes: int) -> Iterator[Dict]:
    """Yield PyTerrier-acceptable dicts from files under root."""
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in ALLOWED_SUFFIXES:
            continue

        parsed = parse_file(fp, max_bytes)
        content = parsed.get("content", "")
        meta = parsed.get("metadata", {}) or {}

        # Basic title guess
        title = meta.get("title") or fp.stem
        ctype = meta.get("Content-Type") or meta.get("Content-type") or ""
        mtime = datetime.fromtimestamp(fp.stat().st_mtime).isoformat(timespec="seconds")

        # PyTerrier doc fields
        yield {
            "docno": str(fp),           # unique ID = absolute path
            "path": str(fp),
            "title": title,
            "text": content,            # <-- add this line
            "content": content,         # optional: keep full body as meta too
            "content_type": ctype,
            "modified": mtime,
        }

