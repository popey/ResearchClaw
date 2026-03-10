"""Semantic Scholar search tool.

Provides functions to search for papers, authors, and citations using
the Semantic Scholar Academic Graph API.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Semantic Scholar API fields
_PAPER_FIELDS = [
    "title",
    "abstract",
    "year",
    "authors",
    "venue",
    "citationCount",
    "referenceCount",
    "externalIds",
    "url",
    "openAccessPdf",
    "fieldsOfStudy",
    "publicationDate",
    "tldr",
]

_SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except Exception:
        return 0.0


def _semantic_scholar_get(
    path: str,
    *,
    params: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    import httpx

    headers = {
        "User-Agent": "ResearchClaw/1.0",
    }
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key

    max_attempts = 4
    backoff_base = 1.5

    with httpx.Client(timeout=timeout, headers=headers) as client:
        for attempt in range(max_attempts):
            resp = client.get(f"{_SEMANTIC_SCHOLAR_BASE}{path}", params=params)

            if resp.status_code == 429 and attempt < max_attempts - 1:
                retry_after = _retry_after_seconds(
                    resp.headers.get("Retry-After"),
                )
                sleep_s = (
                    retry_after
                    if retry_after > 0
                    else backoff_base * (2**attempt)
                )
                time.sleep(min(max(1.0, sleep_s), 20.0))
                continue

            if resp.status_code >= 500 and attempt < max_attempts - 1:
                time.sleep(min(backoff_base * (2**attempt), 12.0))
                continue

            resp.raise_for_status()
            return resp.json()

    # Should never reach here because raise_for_status() is called above.
    return {}


def semantic_scholar_search(
    query: str,
    max_results: int = 10,
    year_range: Optional[str] = None,
    fields_of_study: Optional[list[str]] = None,
    min_citation_count: int = 0,
) -> list[dict[str, Any]]:
    """Search Semantic Scholar for academic papers.

    Parameters
    ----------
    query:
        Natural language search query.
    max_results:
        Maximum number of results (default 10, max 100).
    year_range:
        Optional year filter, e.g. ``"2020-2024"`` or ``"2023-"``.
    fields_of_study:
        Optional list of fields, e.g. ``["Computer Science", "Mathematics"]``.
    min_citation_count:
        Minimum citation count filter (default 0).

    Returns
    -------
    list[dict]
        List of paper metadata dicts.
    """
    try:
        max_results = max(1, min(int(max_results or 10), 100))

        params: dict[str, Any] = {
            "query": query,
            "limit": max_results,
            "fields": ",".join(_PAPER_FIELDS),
        }

        if year_range:
            params["year"] = year_range
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        if min_citation_count > 0:
            params["minCitationCount"] = min_citation_count

        data = _semantic_scholar_get(
            "/paper/search",
            params=params,
            timeout=30.0,
        )

        results = []
        for paper in data.get("data", []):
            authors = [a.get("name", "") for a in paper.get("authors", [])]
            external_ids = paper.get("externalIds", {})

            result = {
                "title": paper.get("title", ""),
                "authors": authors,
                "abstract": paper.get("abstract", ""),
                "year": paper.get("year"),
                "venue": paper.get("venue", ""),
                "citation_count": paper.get("citationCount", 0),
                "reference_count": paper.get("referenceCount", 0),
                "url": paper.get("url", ""),
                "doi": external_ids.get("DOI", ""),
                "arxiv_id": external_ids.get("ArXiv", ""),
                "fields_of_study": paper.get("fieldsOfStudy") or [],
                "publication_date": paper.get("publicationDate", ""),
                "paper_id": paper.get("paperId", ""),
            }

            # Add TLDR if available
            tldr = paper.get("tldr")
            if tldr and isinstance(tldr, dict):
                result["tldr"] = tldr.get("text", "")

            # Add open access PDF URL
            oa_pdf = paper.get("openAccessPdf")
            if oa_pdf and isinstance(oa_pdf, dict):
                result["pdf_url"] = oa_pdf.get("url", "")

            results.append(result)

        return results

    except ImportError:
        return [
            {"error": "httpx package not installed. Run: pip install httpx"},
        ]
    except Exception as e:
        if "429" in str(e):
            return [
                {
                    "error": (
                        "Semantic Scholar is rate-limiting requests (HTTP 429). "
                        "Please retry later, reduce request frequency, or configure "
                        "SEMANTIC_SCHOLAR_API_KEY for higher quota."
                    ),
                },
            ]
        logger.exception("Semantic Scholar search failed")
        return [{"error": f"Semantic Scholar search failed: {e}"}]


def semantic_scholar_get_paper(paper_id: str) -> dict[str, Any]:
    """Get detailed information about a specific paper.

    Parameters
    ----------
    paper_id:
        Semantic Scholar paper ID, DOI, ArXiv ID, or URL.
        Examples: ``"649def34f8be52c8b66281af98ae884c09aef38b"``,
        ``"DOI:10.18653/v1/N18-3011"``, ``"ArXiv:2106.15928"``.

    Returns
    -------
    dict
        Detailed paper information.
    """
    try:
        fields = ",".join(_PAPER_FIELDS + ["citations", "references"])
        paper = _semantic_scholar_get(
            f"/paper/{paper_id}",
            params={"fields": fields},
            timeout=30.0,
        )

        authors = [a.get("name", "") for a in paper.get("authors", [])]

        return {
            "title": paper.get("title", ""),
            "authors": authors,
            "abstract": paper.get("abstract", ""),
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "citation_count": paper.get("citationCount", 0),
            "reference_count": paper.get("referenceCount", 0),
            "url": paper.get("url", ""),
            "fields_of_study": paper.get("fieldsOfStudy") or [],
            "citations_sample": [
                {
                    "title": c.get("title", ""),
                    "year": c.get("year"),
                }
                for c in (paper.get("citations") or [])[:10]
            ],
            "references_sample": [
                {
                    "title": r.get("title", ""),
                    "year": r.get("year"),
                }
                for r in (paper.get("references") or [])[:10]
            ],
        }

    except Exception as e:
        logger.exception("Semantic Scholar paper fetch failed")
        return {"error": f"Failed to fetch paper: {e}"}


def semantic_scholar_citations(
    paper_id: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Get papers that cite a given paper.

    Parameters
    ----------
    paper_id:
        Semantic Scholar paper ID, DOI, or ArXiv ID.
    max_results:
        Maximum number of citing papers to return.

    Returns
    -------
    list[dict]
        List of citing paper metadata.
    """
    try:
        data = _semantic_scholar_get(
            f"/paper/{paper_id}/citations",
            params={
                "fields": "title,authors,year,venue,citationCount,url",
                "limit": min(max(max_results, 1), 100),
            },
            timeout=30.0,
        )

        return [
            {
                "title": c["citingPaper"].get("title", ""),
                "authors": [
                    a.get("name", "")
                    for a in c["citingPaper"].get("authors", [])
                ],
                "year": c["citingPaper"].get("year"),
                "venue": c["citingPaper"].get("venue", ""),
                "citation_count": c["citingPaper"].get("citationCount", 0),
            }
            for c in data.get("data", [])
        ]

    except Exception as e:
        logger.exception("Citation fetch failed")
        return [{"error": f"Failed to fetch citations: {e}"}]
