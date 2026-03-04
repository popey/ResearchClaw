"""Data schemas shared across the agents module."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from typing import Literal, Optional, Required, TypedDict
else:
    from typing import Literal, Optional, TypedDict

    from typing_extensions import Required


class Base64Source(TypedDict, total=False):
    """Inline Base64 file source."""

    type: Required[Literal["base64"]]
    media_type: Required[str]
    data: Required[str]


class URLSource(TypedDict, total=False):
    """URL-based file source."""

    type: Required[Literal["url"]]
    url: Required[str]


class FileBlock(TypedDict, total=False):
    """Standardised block for returning files from tool results.

    Supports both inline Base64 data and external URLs.
    """

    type: Required[Literal["file", "image", "audio", "video"]]
    source: Required[Base64Source | URLSource]
    filename: Optional[str]


class PaperInfo(TypedDict, total=False):
    """Structured paper metadata returned by search tools."""

    title: Required[str]
    authors: list[str]
    abstract: str
    year: int
    venue: str
    doi: str
    arxiv_id: str
    url: str
    citation_count: int
    pdf_url: str
    bibtex: str


class ExperimentRecord(TypedDict, total=False):
    """Record for experiment tracking."""

    experiment_id: Required[str]
    name: Required[str]
    parameters: dict
    metrics: dict
    notes: str
    timestamp: str
    tags: list[str]
