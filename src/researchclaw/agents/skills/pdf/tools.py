"""PDF paper reader tools."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from ....constant import PAPERS_DIR

logger = logging.getLogger(__name__)


def read_paper(
    source: str,
    extract_references: bool = False,
    max_pages: Optional[int] = None,
    sections: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Read and extract content from a PDF paper."""
    filepath = _resolve_source(source)
    if filepath is None:
        return {"error": f"Could not resolve paper source: {source}"}

    if not Path(filepath).exists():
        return {"error": f"File not found: {filepath}"}

    try:
        return _extract_with_pdfplumber(
            filepath,
            extract_references,
            max_pages,
            sections,
        )
    except ImportError:
        pass

    try:
        return _extract_with_pypdf2(
            filepath,
            extract_references,
            max_pages,
            sections,
        )
    except ImportError:
        return {
            "error": "No PDF library available. Install: pip install pdfplumber PyPDF2",
        }


def _resolve_source(source: str) -> Optional[str]:
    if os.path.isfile(source):
        return source

    papers_path = Path(PAPERS_DIR) / source
    if papers_path.exists():
        return str(papers_path)

    import re

    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", source):
        pdf_name = f"{source.replace('/', '_')}.pdf"
        cached = Path(PAPERS_DIR) / pdf_name
        if cached.exists():
            return str(cached)

        try:
            from ..arxiv.tools import arxiv_download

            result = arxiv_download(source)
            if "path" in result:
                return result["path"]
        except Exception:
            logger.debug("Could not download ArXiv paper %s", source)

    if source.startswith("http://") or source.startswith("https://"):
        try:
            import httpx

            os.makedirs(PAPERS_DIR, exist_ok=True)
            filename = source.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"
            filepath = Path(PAPERS_DIR) / filename

            with httpx.stream(
                "GET",
                source,
                timeout=60,
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            return str(filepath)
        except Exception as e:
            logger.debug("Could not download PDF from URL: %s", e)

    return None


def _extract_with_pdfplumber(
    filepath: str,
    extract_references: bool,
    max_pages: Optional[int],
    sections: Optional[list[str]],
) -> dict[str, Any]:
    import pdfplumber

    result: dict[str, Any] = {
        "text": "",
        "metadata": {},
        "page_count": 0,
        "tables": [],
    }

    with pdfplumber.open(filepath) as pdf:
        result["page_count"] = len(pdf.pages)
        result["metadata"] = pdf.metadata or {}

        pages_to_read = pdf.pages[:max_pages] if max_pages else pdf.pages
        all_text_parts: list[str] = []

        for i, page in enumerate(pages_to_read):
            text = page.extract_text() or ""
            all_text_parts.append(f"--- Page {i + 1} ---\n{text}")

            tables = page.extract_tables()
            for table in tables:
                if table:
                    result["tables"].append({"page": i + 1, "data": table})

        result["text"] = "\n\n".join(all_text_parts)

    if sections:
        result["sections"] = _extract_sections(result["text"], sections)
    if extract_references:
        result["references"] = _extract_references(result["text"])

    return result


def _extract_with_pypdf2(
    filepath: str,
    extract_references: bool,
    max_pages: Optional[int],
    sections: Optional[list[str]],
) -> dict[str, Any]:
    from PyPDF2 import PdfReader

    reader = PdfReader(filepath)
    result: dict[str, Any] = {
        "text": "",
        "metadata": {},
        "page_count": len(reader.pages),
        "tables": [],
    }

    if reader.metadata:
        result["metadata"] = {
            "title": reader.metadata.title or "",
            "author": reader.metadata.author or "",
            "subject": reader.metadata.subject or "",
            "creator": reader.metadata.creator or "",
        }

    pages_to_read = reader.pages[:max_pages] if max_pages else reader.pages
    all_text_parts: list[str] = []

    for i, page in enumerate(pages_to_read):
        text = page.extract_text() or ""
        all_text_parts.append(f"--- Page {i + 1} ---\n{text}")

    result["text"] = "\n\n".join(all_text_parts)

    if sections:
        result["sections"] = _extract_sections(result["text"], sections)
    if extract_references:
        result["references"] = _extract_references(result["text"])

    return result


def _extract_sections(
    full_text: str,
    section_names: list[str],
) -> dict[str, str]:
    import re

    extracted: dict[str, str] = {}
    for name in section_names:
        patterns = [
            rf"(?:^|\n)\s*(?:\d+\.?\s+)?{re.escape(name)}\s*\n(.*?)(?=\n\s*(?:\d+\.?\s+)?[A-Z][a-z]+|\Z)",
            rf"(?:^|\n)\s*{re.escape(name.upper())}\s*\n(.*?)(?=\n\s*[A-Z][A-Z]+|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
            if match:
                extracted[name] = match.group(1).strip()[:5000]
                break

    return extracted


def _extract_references(full_text: str) -> list[str]:
    import re

    ref_match = re.search(
        r"(?:^|\n)\s*(?:References|Bibliography|REFERENCES)\s*\n(.*)$",
        full_text,
        re.DOTALL,
    )
    if not ref_match:
        return []

    ref_text = ref_match.group(1).strip()
    refs = re.split(r"\n\s*(?:\[\d+\]|\d+\.\s+)", ref_text)
    return [ref.strip()[:1000] for ref in refs if ref.strip()]


__all__ = ["read_paper"]
