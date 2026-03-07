"""Browser tools for web browsing and information gathering.

This module supports two runtime modes for ``browser_use``:
- Playwright mode (interactive): start/open/snapshot/click/type/... via browser
- HTTP fallback mode: open/snapshot via ``browse_url`` when Playwright is absent
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_BROWSER_SESSION: dict[str, Any] = {
    "running": False,
    "headed": False,
    "backend": "http",
    "last_url": "",
    "last_result": None,
    "playwright": None,
    "browser": None,
    "context": None,
    "pages": {},
    "refs": {},
}


def browse_url(
    url: str,
    extract_text: bool = True,
    screenshot: bool = False,
    wait_seconds: int = 3,
) -> dict[str, Any]:
    """Open a URL and extract content.

    Parameters
    ----------
    url:
        The URL to visit.
    extract_text:
        Whether to extract page text content.
    screenshot:
        Whether to take a screenshot.
    wait_seconds:
        Seconds to wait for page load.

    Returns
    -------
    dict
        Result with ``title``, ``text``, ``url``, and optionally ``screenshot_base64``.
    """
    try:
        import httpx

        # Simple HTTP fetch for text extraction
        resp = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "ResearchClaw/1.0 (Academic Research Assistant)",
            },
        )
        resp.raise_for_status()

        result: dict[str, Any] = {
            "url": str(resp.url),
            "status_code": resp.status_code,
        }

        if extract_text:
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                result["text"] = _extract_text_from_html(resp.text)
                result["title"] = _extract_title_from_html(resp.text)
            else:
                text = resp.text
                if len(text) > 200_000:
                    text = text[:200_000] + "\n... [truncated]"
                result["text"] = text
                result["title"] = ""

        return result

    except ImportError:
        return {"error": "httpx not installed. Run: pip install httpx"}
    except Exception as e:
        logger.exception("Browse failed")
        return {"error": f"Failed to browse URL: {e}"}


def browser_use(
    action: str,
    url: Optional[str] = None,
    page_id: str = "default",
    extract_text: bool = True,
    screenshot: bool = False,
    wait_seconds: int = 3,
    headed: bool = False,
    ref: Optional[str] = None,
    selector: Optional[str] = None,
    text: Optional[str] = None,
    value: Optional[str] = None,
    submit: bool = False,
    slowly: bool = False,
    double_click: bool = False,
    button: str = "left",
    interactive: bool = False,
    compact: bool = True,
    max_depth: Optional[int] = None,
) -> dict[str, Any]:
    """CoPaw/OpenClaw-compatible browser tool shim.

    Supported actions:
    - ``start``: mark browser session as started (optionally ``headed=true``)
    - ``open``: fetch URL content (delegates to ``browse_url``)
    - ``snapshot``: return last open result
    - ``click``/``type`` in Playwright mode
    - ``stop``: close session state
    """
    action_norm = (action or "").strip().lower()

    if action_norm == "start":
        _stop_playwright_session()
        started = _try_start_playwright_session(headed=bool(headed))
        _BROWSER_SESSION["running"] = True
        _BROWSER_SESSION["headed"] = bool(headed)
        _BROWSER_SESSION["backend"] = "playwright" if started else "http"
        return {
            "status": "started",
            "headed": bool(headed),
            "backend": _BROWSER_SESSION["backend"],
            "message": (
                "Browser session initialized."
                if started
                else "Playwright unavailable, running in HTTP fallback mode."
            ),
        }

    if action_norm == "stop":
        _stop_playwright_session()
        _BROWSER_SESSION["running"] = False
        _BROWSER_SESSION["headed"] = False
        _BROWSER_SESSION["backend"] = "http"
        _BROWSER_SESSION["last_url"] = ""
        _BROWSER_SESSION["last_result"] = None
        _BROWSER_SESSION["pages"] = {}
        _BROWSER_SESSION["refs"] = {}
        return {"status": "stopped", "message": "Browser session stopped."}

    if action_norm in {"open", "navigate"}:
        if not url:
            return {"error": "browser_use action=open requires `url`"}
        if not _BROWSER_SESSION["running"]:
            _BROWSER_SESSION["running"] = True
            _BROWSER_SESSION["headed"] = bool(headed)
            started = _try_start_playwright_session(headed=bool(headed))
            _BROWSER_SESSION["backend"] = "playwright" if started else "http"

        if _BROWSER_SESSION["backend"] == "playwright":
            page = _get_or_create_page(page_id=page_id)
            if page is None:
                return {
                    "error": "Playwright browser is not available.",
                    "hint": "Install playwright and run: python -m playwright install",
                }
            try:
                page.goto(url, timeout=max(wait_seconds, 1) * 1000)
                if wait_seconds > 0:
                    page.wait_for_timeout(wait_seconds * 1000)
                title = page.title() or ""
                page_text = ""
                if extract_text:
                    page_text = page.inner_text("body")
                    if len(page_text) > 200_000:
                        page_text = page_text[:200_000] + "\n... [truncated]"
                result: dict[str, Any] = {
                    "url": page.url,
                    "title": title,
                    "text": page_text,
                    "page_id": page_id,
                }
                if screenshot:
                    import base64

                    shot = page.screenshot(full_page=True)
                    result["screenshot_base64"] = base64.b64encode(shot).decode(
                        "utf-8",
                    )
            except Exception as e:
                return {"error": f"Failed to open URL in browser: {e}"}
        else:
            result = browse_url(
                url=url,
                extract_text=extract_text,
                screenshot=screenshot,
                wait_seconds=wait_seconds,
            )

        _BROWSER_SESSION["last_url"] = url
        _BROWSER_SESSION["last_result"] = result
        return {
            "status": "opened",
            "url": url,
            "headed": _BROWSER_SESSION["headed"],
            "backend": _BROWSER_SESSION["backend"],
            "result": result,
        }

    if action_norm == "snapshot":
        if _BROWSER_SESSION["backend"] == "playwright":
            page = _get_or_create_page(page_id=page_id, create=False)
            if page is None:
                return {
                    "error": "No active page. Call browser_use action=open first.",
                }
            try:
                from .browser_snapshot import build_role_snapshot_from_aria

                aria_snapshot = page.locator("body").aria_snapshot()
                snapshot_text, refs = build_role_snapshot_from_aria(
                    aria_snapshot,
                    interactive=interactive,
                    compact=compact,
                    max_depth=max_depth,
                )
                _BROWSER_SESSION["refs"][page_id] = refs
                result = {
                    "url": page.url,
                    "title": page.title() or "",
                    "page_id": page_id,
                    "snapshot": snapshot_text,
                    "refs_count": len(refs),
                }
                _BROWSER_SESSION["last_result"] = result
                _BROWSER_SESSION["last_url"] = page.url
                return {
                    "status": "snapshot",
                    "backend": "playwright",
                    "result": result,
                }
            except Exception as e:
                return {"error": f"Failed to snapshot page: {e}"}

        last = _BROWSER_SESSION.get("last_result")
        if not last:
            return {
                "error": "No page snapshot available. Call browser_use action=open first.",
            }
        return {
            "status": "snapshot",
            "url": _BROWSER_SESSION.get("last_url", ""),
            "backend": _BROWSER_SESSION["backend"],
            "result": last,
        }

    if action_norm == "screenshot":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {
                "error": "screenshot requires Playwright runtime. Use action=open with screenshot=true in HTTP mode.",
            }
        page = _get_or_create_page(page_id=page_id, create=False)
        if page is None:
            return {"error": "No active page. Call browser_use action=open first."}
        try:
            import base64

            shot = page.screenshot(full_page=True)
            return {
                "status": "screenshot",
                "backend": "playwright",
                "image_base64": base64.b64encode(shot).decode("utf-8"),
            }
        except Exception as e:
            return {"error": f"Failed to capture screenshot: {e}"}

    if action_norm in {"click", "type", "fill", "press", "scroll", "hover"}:
        if _BROWSER_SESSION["backend"] != "playwright":
            return {
                "error": (
                    f"browser_use action={action_norm} requires Playwright. "
                    "Install playwright and run: python -m playwright install"
                ),
            }

        page = _get_or_create_page(page_id=page_id, create=False)
        if page is None:
            return {"error": "No active page. Call browser_use action=open first."}
        locator = _resolve_locator(page_id=page_id, page=page, ref=ref, selector=selector)
        if locator is None:
            return {
                "error": "Cannot find target element. Provide `ref` from snapshot or `selector`.",
            }

        try:
            if action_norm == "click":
                if double_click:
                    locator.dblclick(button=button)
                else:
                    locator.click(button=button)
            elif action_norm in {"type", "fill"}:
                input_text = text if text is not None else (value or "")
                if slowly:
                    locator.click()
                    for ch in input_text:
                        locator.type(ch)
                        time.sleep(0.03)
                else:
                    locator.fill(input_text)
                if submit:
                    page.keyboard.press("Enter")
            elif action_norm == "press":
                key = text if text is not None else (value or "")
                if not key:
                    return {"error": "press action requires key in `text` or `value`"}
                page.keyboard.press(key)
            elif action_norm == "scroll":
                page.mouse.wheel(0, 800)
            elif action_norm == "hover":
                locator.hover()

            return {
                "status": action_norm,
                "backend": "playwright",
                "page_id": page_id,
            }
        except Exception as e:
            return {"error": f"Failed action {action_norm}: {e}"}

    if action_norm == "tabs":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"status": "tabs", "backend": "http", "tabs": []}
        pages = _BROWSER_SESSION.get("pages", {})
        tab_info = []
        for pid, page in pages.items():
            tab_info.append(
                {
                    "page_id": pid,
                    "url": getattr(page, "url", ""),
                    "title": page.title() if page else "",
                },
            )
        return {"status": "tabs", "backend": "playwright", "tabs": tab_info}

    if action_norm == "wait_for":
        if _BROWSER_SESSION["backend"] != "playwright":
            time.sleep(max(wait_seconds, 0))
            return {"status": "wait_for", "backend": "http", "seconds": wait_seconds}
        page = _get_or_create_page(page_id=page_id, create=False)
        if page is None:
            return {"error": "No active page. Call browser_use action=open first."}
        try:
            page.wait_for_timeout(max(wait_seconds, 0) * 1000)
            return {
                "status": "wait_for",
                "backend": "playwright",
                "seconds": wait_seconds,
            }
        except Exception as e:
            return {"error": f"Failed wait_for: {e}"}

    if action_norm in {"eval", "evaluate", "run_code"}:
        if _BROWSER_SESSION["backend"] != "playwright":
            return {
                "error": f"browser_use action={action_norm} requires Playwright runtime.",
            }
        return {
            "error": f"browser_use action={action_norm} is not implemented in ResearchClaw yet.",
        }

    if action_norm in {"navigate_back", "close", "handle_dialog", "file_upload", "fill_form", "install", "press_key", "network_requests", "drag", "select_option", "pdf", "resize", "console_messages"}:
        return {
            "error": (
                f"browser_use action={action_norm} is not implemented in this runtime. "
                "Supported now: start, stop, open/navigate, snapshot, screenshot, click, type/fill, press, scroll, hover, tabs, wait_for."
            ),
            "hints": {
                "ref": ref,
                "selector": selector,
                "text": text or value,
            },
        }

    return {
        "error": (
            f"Unsupported browser_use action: {action_norm}. "
            "Supported actions: start, stop, open/navigate, snapshot, screenshot, click, type/fill, press, scroll, hover, tabs, wait_for."
        ),
    }


def _try_start_playwright_session(*, headed: bool) -> bool:
    """Best-effort Playwright startup for interactive browser_use actions."""
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context()
        _BROWSER_SESSION["playwright"] = playwright
        _BROWSER_SESSION["browser"] = browser
        _BROWSER_SESSION["context"] = context
        _BROWSER_SESSION["pages"] = {}
        _BROWSER_SESSION["refs"] = {}
        return True
    except Exception:
        logger.debug("Playwright unavailable; fallback to HTTP mode", exc_info=True)
        _stop_playwright_session()
        return False


def _stop_playwright_session() -> None:
    """Close Playwright resources safely."""
    try:
        context = _BROWSER_SESSION.get("context")
        if context is not None:
            context.close()
    except Exception:
        pass
    try:
        browser = _BROWSER_SESSION.get("browser")
        if browser is not None:
            browser.close()
    except Exception:
        pass
    try:
        playwright = _BROWSER_SESSION.get("playwright")
        if playwright is not None:
            playwright.stop()
    except Exception:
        pass
    _BROWSER_SESSION["playwright"] = None
    _BROWSER_SESSION["browser"] = None
    _BROWSER_SESSION["context"] = None
    _BROWSER_SESSION["pages"] = {}
    _BROWSER_SESSION["refs"] = {}


def _get_or_create_page(page_id: str, *, create: bool = True):
    """Return existing Playwright page by id, creating one if requested."""
    pages = _BROWSER_SESSION.get("pages", {})
    if page_id in pages:
        return pages[page_id]
    if not create:
        return None
    context = _BROWSER_SESSION.get("context")
    if context is None:
        return None
    page = context.new_page()
    pages[page_id] = page
    _BROWSER_SESSION["pages"] = pages
    return page


def _resolve_locator(page_id: str, page: Any, ref: Optional[str], selector: Optional[str]):
    """Resolve a target locator from ref or selector."""
    if selector:
        return page.locator(selector)
    if ref:
        page_refs = _BROWSER_SESSION.get("refs", {}).get(page_id, {})
        meta = page_refs.get(ref)
        if meta:
            role = meta.get("role")
            name = meta.get("name")
            nth = int(meta.get("nth", 0) or 0)
            locator = page.get_by_role(role, name=name) if name else page.get_by_role(role)
            if nth > 0:
                locator = locator.nth(nth)
            return locator
    return None


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML."""
    import re

    # Remove scripts and styles
    text = re.sub(
        r"<script[^>]*>.*?</script>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<style[^>]*>.*?</style>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate
    if len(text) > 200_000:
        text = text[:200_000] + "\n... [truncated]"
    return text


def _extract_title_from_html(html: str) -> str:
    """Extract the page title from HTML."""
    import re

    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""
