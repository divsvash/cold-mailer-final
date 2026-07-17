"""File reading utilities — PDF text extraction and markdown reading."""
from __future__ import annotations
import pathlib
from pdfminer.high_level import extract_text as _pdf_extract_text
from pdfminer.pdfparser import PDFSyntaxError


def read_pdf(path: str | pathlib.Path) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
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
    return p.read_text(encoding="utf-8")
