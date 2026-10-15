"""File reading utilities — PDF text extraction and markdown reading."""
from __future__ import annotations
import pathlib
from pdfminer.high_level import extract_text as _pdf_extract_text
from pdfminer.pdfparser import PDFSyntaxError


def read_pdf(path: str | pathlib.Path) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if p.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("PDF exceeds the 10 MiB input limit")
    try:
        text = _pdf_extract_text(str(p))
    except PDFSyntaxError as exc:
        raise ValueError(f"Could not parse PDF {path}: {exc}") from exc
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"PDF {path} has no extractable text layer.")
    return stripped


def read_md(path: str | pathlib.Path) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")
    if p.stat().st_size > 1024 * 1024:
        raise ValueError("Markdown exceeds the 1 MiB input limit")
    return p.read_text(encoding="utf-8")
