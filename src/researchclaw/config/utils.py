"""Configuration utility helpers."""

from __future__ import annotations


def merge_config(base: dict, updates: dict) -> dict:
    merged = dict(base)
    merged.update(updates)
    return merged
