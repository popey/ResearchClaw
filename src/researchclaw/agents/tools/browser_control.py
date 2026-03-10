"""Browser tools for web browsing and information gathering.

This module supports two runtime modes for ``browser_use``:
- Playwright mode (interactive): start/open/snapshot/click/type/... via browser
- HTTP fallback mode: open/snapshot via ``browse_url`` when Playwright is absent
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
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
    "current_page_id": "default",
    "console_logs": {},
    "network_logs": {},
    "dialog_policy": {},
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


def _parse_json_param(value: Optional[str], default: Any = None) -> Any:
    """Parse optional JSON string parameter."""
    if value is None:
        return default
    raw = value.strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        if "," in raw:
            return [p.strip() for p in raw.split(",") if p.strip()]
        return default


def _append_console_log(page_id: str, level: str, text: str) -> None:
    logs = _BROWSER_SESSION.setdefault("console_logs", {}).setdefault(
        page_id,
        [],
    )
    logs.append({"level": level, "text": text, "ts": time.time()})
    if len(logs) > 300:
        del logs[: len(logs) - 300]


def _append_network_log(
    page_id: str,
    *,
    url: str,
    method: str,
    resource_type: str,
    status: Optional[int],
    ok: bool,
) -> None:
    logs = _BROWSER_SESSION.setdefault("network_logs", {}).setdefault(
        page_id,
        [],
    )
    logs.append(
        {
            "url": url,
            "method": method,
            "resource_type": resource_type,
            "status": status,
            "ok": ok,
            "ts": time.time(),
        },
    )
    if len(logs) > 600:
        del logs[: len(logs) - 600]


def _attach_page_handlers(page_id: str, page: Any) -> None:
    """Attach console/network/dialog handlers to a Playwright page."""

    def _on_console(msg: Any) -> None:
        try:
            _append_console_log(
                page_id,
                level=str(getattr(msg, "type", "info")),
                text=str(msg.text),
            )
        except Exception:
            logger.debug("console handler failed", exc_info=True)

    def _on_request_finished(req: Any) -> None:
        try:
            resp = req.response()
            status = int(resp.status) if resp is not None else None
            _append_network_log(
                page_id,
                url=str(req.url),
                method=str(req.method),
                resource_type=str(req.resource_type),
                status=status,
                ok=(status is not None and status < 400),
            )
        except Exception:
            logger.debug("requestfinished handler failed", exc_info=True)

    def _on_request_failed(req: Any) -> None:
        try:
            _append_network_log(
                page_id,
                url=str(req.url),
                method=str(req.method),
                resource_type=str(req.resource_type),
                status=None,
                ok=False,
            )
        except Exception:
            logger.debug("requestfailed handler failed", exc_info=True)

    def _on_dialog(dialog: Any) -> None:
        policy = _BROWSER_SESSION.get("dialog_policy", {}).get(
            page_id,
            {"accept": True, "prompt_text": ""},
        )
        try:
            if bool(policy.get("accept", True)):
                dialog.accept(str(policy.get("prompt_text", "") or ""))
                _append_console_log(
                    page_id,
                    "dialog",
                    f"Accepted dialog: {dialog.type}",
                )
            else:
                dialog.dismiss()
                _append_console_log(
                    page_id,
                    "dialog",
                    f"Dismissed dialog: {dialog.type}",
                )
        except Exception:
            logger.debug("dialog handler failed", exc_info=True)

    page.on("console", _on_console)
    page.on("requestfinished", _on_request_finished)
    page.on("requestfailed", _on_request_failed)
    page.on("dialog", _on_dialog)


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
        _BROWSER_SESSION["console_logs"] = {}
        _BROWSER_SESSION["network_logs"] = {}
        _BROWSER_SESSION["dialog_policy"] = {}
        _BROWSER_SESSION["current_page_id"] = "default"
        return True
    except Exception:
        logger.debug(
            "Playwright unavailable; fallback to HTTP mode",
            exc_info=True,
        )
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
    _BROWSER_SESSION["console_logs"] = {}
    _BROWSER_SESSION["network_logs"] = {}
    _BROWSER_SESSION["dialog_policy"] = {}


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
    _BROWSER_SESSION["current_page_id"] = page_id
    _attach_page_handlers(page_id, page)
    return page


def _resolve_locator(
    page_id: str,
    page: Any,
    ref: Optional[str],
    selector: Optional[str],
):
    """Resolve a locator from ref or selector."""
    if selector:
        return page.locator(selector)
    if ref:
        page_refs = _BROWSER_SESSION.get("refs", {}).get(page_id, {})
        meta = page_refs.get(ref)
        if meta:
            role = meta.get("role")
            name = meta.get("name")
            nth = int(meta.get("nth", 0) or 0)
            try:
                locator = (
                    page.get_by_role(role, name=name)
                    if name
                    else page.get_by_role(role)
                )
                if nth > 0:
                    locator = locator.nth(nth)
                return locator
            except Exception:
                pass
    return None


def _collect_tabs() -> list[dict[str, Any]]:
    tabs: list[dict[str, Any]] = []
    pages = _BROWSER_SESSION.get("pages", {})
    for pid, page in pages.items():
        title = ""
        url = ""
        try:
            title = str(page.title() or "")
        except Exception:
            pass
        try:
            url = str(page.url)
        except Exception:
            pass
        tabs.append({"page_id": pid, "title": title, "url": url})
    return tabs


def _safe_output_path(path_or_name: Optional[str], suffix: str) -> str:
    if path_or_name and path_or_name.strip():
        p = Path(path_or_name).expanduser()
        if not p.suffix:
            p = p.with_suffix(suffix)
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p.resolve())
    _fd, tmp = tempfile.mkstemp(prefix="researchclaw_browser_", suffix=suffix)
    Path(tmp).unlink(missing_ok=True)
    Path(tmp).parent.mkdir(parents=True, exist_ok=True)
    return tmp


def browser_use(  # pylint: disable=too-many-branches,too-many-return-statements,too-many-arguments
    action: str,
    url: str = "",
    page_id: str = "default",
    selector: str = "",
    text: str = "",
    code: str = "",
    path: str = "",
    wait: int = 0,
    full_page: bool = False,
    width: int = 0,
    height: int = 0,
    level: str = "info",
    filename: str = "",
    accept: bool = True,
    prompt_text: str = "",
    ref: str = "",
    element: str = "",
    paths_json: str = "",
    fields_json: str = "",
    key: str = "",
    submit: bool = False,
    slowly: bool = False,
    include_static: bool = False,
    screenshot_type: str = "png",
    snapshot_filename: str = "",
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    start_ref: str = "",
    end_ref: str = "",
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",
    end_element: str = "",
    values_json: str = "",
    tab_action: str = "",
    index: int = -1,
    wait_time: float = 0,
    text_gone: str = "",
    frame_selector: str = "",
    headed: bool = False,
    extract_text: bool = True,
    screenshot: bool = False,
    wait_seconds: int = 3,
    value: str = "",
    interactive: bool = False,
    compact: bool = True,
    max_depth: Optional[int] = None,
) -> dict[str, Any]:
    """CoPaw/OpenClaw-compatible browser tool implementation.

    Supports most common browser actions used by CoPaw-style skills.
    In environments without Playwright, falls back to HTTP-only mode.
    """
    action_norm = (action or "").strip().lower()
    effective_page_id = page_id or str(
        _BROWSER_SESSION.get("current_page_id", "default"),
    )

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
        return {"status": "stopped", "message": "Browser session stopped."}

    if not _BROWSER_SESSION.get("running"):
        _BROWSER_SESSION["running"] = True
        _BROWSER_SESSION["headed"] = bool(headed)
        started = _try_start_playwright_session(headed=bool(headed))
        _BROWSER_SESSION["backend"] = "playwright" if started else "http"

    if action_norm in {"open", "navigate"}:
        if not url:
            return {"error": "browser_use action=open requires `url`"}

        if _BROWSER_SESSION["backend"] == "playwright":
            page = _get_or_create_page(effective_page_id, create=True)
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
                    "page_id": effective_page_id,
                }
                if screenshot:
                    import base64

                    shot = page.screenshot(full_page=True)
                    result["screenshot_base64"] = base64.b64encode(
                        shot,
                    ).decode("utf-8")
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
        _BROWSER_SESSION["current_page_id"] = effective_page_id
        return {
            "status": "opened",
            "url": url,
            "headed": _BROWSER_SESSION["headed"],
            "backend": _BROWSER_SESSION["backend"],
            "result": result,
        }

    if action_norm == "navigate_back":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "navigate_back requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        try:
            page.go_back()
            return {
                "status": "navigate_back",
                "backend": "playwright",
                "url": page.url,
                "page_id": effective_page_id,
            }
        except Exception as e:
            return {"error": f"Failed navigate_back: {e}"}

    if action_norm == "snapshot":
        if _BROWSER_SESSION["backend"] == "playwright":
            page = _get_or_create_page(effective_page_id, create=False)
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
                _BROWSER_SESSION["refs"][effective_page_id] = refs
                result = {
                    "url": page.url,
                    "title": page.title() or "",
                    "page_id": effective_page_id,
                    "snapshot": snapshot_text,
                    "refs_count": len(refs),
                }
                if snapshot_filename:
                    out_path = _safe_output_path(snapshot_filename, ".txt")
                    Path(out_path).write_text(snapshot_text, encoding="utf-8")
                    result["snapshot_path"] = out_path
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
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        try:
            import base64

            out_path = _safe_output_path(
                path or filename,
                ".png" if screenshot_type == "png" else ".jpg",
            )
            shot = page.screenshot(path=out_path, full_page=bool(full_page))
            return {
                "status": "screenshot",
                "backend": "playwright",
                "path": out_path,
                "image_base64": base64.b64encode(shot).decode("utf-8"),
            }
        except Exception as e:
            return {"error": f"Failed to capture screenshot: {e}"}

    if action_norm in {
        "click",
        "type",
        "fill",
        "press",
        "press_key",
        "scroll",
        "hover",
    }:
        if _BROWSER_SESSION["backend"] != "playwright":
            return {
                "error": (
                    f"browser_use action={action_norm} requires Playwright. "
                    "Install playwright and run: python -m playwright install"
                ),
            }

        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }

        locator = _resolve_locator(
            page_id=effective_page_id,
            page=page,
            ref=(ref or "") or None,
            selector=(selector or "") or None,
        )

        try:
            if action_norm == "click":
                if locator is None:
                    return {
                        "error": "Cannot find target element. Provide `ref` from snapshot or `selector`.",
                    }
                if double_click:
                    locator.dblclick(button=button)
                else:
                    locator.click(button=button)
                if wait > 0:
                    page.wait_for_timeout(wait)

            elif action_norm in {"type", "fill"}:
                if locator is None:
                    return {
                        "error": "Cannot find target element. Provide `ref` from snapshot or `selector`.",
                    }
                input_text = text or value or ""
                if slowly:
                    locator.click()
                    for ch in input_text:
                        page.keyboard.type(ch)
                        time.sleep(0.03)
                elif action_norm == "fill":
                    locator.fill(input_text)
                else:
                    locator.type(input_text)
                if submit:
                    page.keyboard.press("Enter")

            elif action_norm in {"press", "press_key"}:
                press_key = key or text or value
                if not press_key:
                    return {
                        "error": "press action requires `key` or `text`/`value`.",
                    }
                page.keyboard.press(str(press_key))

            elif action_norm == "scroll":
                try:
                    dy = int(value or text or 800)
                except Exception:
                    dy = 800
                page.mouse.wheel(0, dy)

            elif action_norm == "hover":
                if locator is None:
                    return {
                        "error": "Cannot find target element. Provide `ref` from snapshot or `selector`.",
                    }
                locator.hover()

            return {
                "status": action_norm,
                "backend": "playwright",
                "page_id": effective_page_id,
            }
        except Exception as e:
            return {"error": f"Failed action {action_norm}: {e}"}

    if action_norm in {"eval", "evaluate", "run_code"}:
        if _BROWSER_SESSION["backend"] != "playwright":
            return {
                "error": f"browser_use action={action_norm} requires Playwright runtime.",
            }
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        script = code or text
        if not script:
            return {
                "error": f"browser_use action={action_norm} requires `code` or `text`.",
            }
        try:
            locator = _resolve_locator(
                page_id=effective_page_id,
                page=page,
                ref=(ref or "") or None,
                selector=(selector or "") or None,
            )
            if locator is not None:
                result = locator.evaluate(script)
            else:
                result = page.evaluate(script)
            return {
                "status": action_norm,
                "backend": "playwright",
                "result": result,
                "page_id": effective_page_id,
            }
        except Exception as e:
            return {"error": f"Failed {action_norm}: {e}"}

    if action_norm == "resize":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "resize requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        if width <= 0 or height <= 0:
            return {"error": "resize requires positive `width` and `height`."}
        try:
            page.set_viewport_size(
                {"width": int(width), "height": int(height)},
            )
            return {
                "status": "resize",
                "backend": "playwright",
                "page_id": effective_page_id,
                "width": int(width),
                "height": int(height),
            }
        except Exception as e:
            return {"error": f"Failed resize: {e}"}

    if action_norm == "console_messages":
        logs = _BROWSER_SESSION.get("console_logs", {}).get(
            effective_page_id,
            [],
        )
        if level:
            logs = [
                m
                for m in logs
                if str(m.get("level", "")).lower() == level.lower()
            ]
        if filename:
            out_path = _safe_output_path(filename, ".json")
            Path(out_path).write_text(
                json.dumps(logs, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {
                "status": "console_messages",
                "backend": _BROWSER_SESSION["backend"],
                "page_id": effective_page_id,
                "count": len(logs),
                "path": out_path,
            }
        return {
            "status": "console_messages",
            "backend": _BROWSER_SESSION["backend"],
            "page_id": effective_page_id,
            "count": len(logs),
            "messages": logs[-100:],
        }

    if action_norm == "network_requests":
        logs = _BROWSER_SESSION.get("network_logs", {}).get(
            effective_page_id,
            [],
        )
        if not include_static:
            dynamic = {"document", "xhr", "fetch", "websocket", "eventsource"}
            logs = [
                m
                for m in logs
                if str(m.get("resource_type", "")).lower() in dynamic
            ]
        if filename:
            out_path = _safe_output_path(filename, ".json")
            Path(out_path).write_text(
                json.dumps(logs, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {
                "status": "network_requests",
                "backend": _BROWSER_SESSION["backend"],
                "page_id": effective_page_id,
                "count": len(logs),
                "path": out_path,
            }
        return {
            "status": "network_requests",
            "backend": _BROWSER_SESSION["backend"],
            "page_id": effective_page_id,
            "count": len(logs),
            "requests": logs[-200:],
        }

    if action_norm == "handle_dialog":
        _BROWSER_SESSION.setdefault("dialog_policy", {})[effective_page_id] = {
            "accept": bool(accept),
            "prompt_text": str(prompt_text or ""),
        }
        return {
            "status": "handle_dialog",
            "backend": _BROWSER_SESSION["backend"],
            "page_id": effective_page_id,
            "policy": _BROWSER_SESSION["dialog_policy"][effective_page_id],
        }

    if action_norm == "file_upload":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "file_upload requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        locator = _resolve_locator(
            page_id=effective_page_id,
            page=page,
            ref=(ref or "") or None,
            selector=(selector or "") or None,
        )
        if locator is None:
            return {"error": "file_upload requires `selector` or `ref`."}

        parsed_paths = _parse_json_param(paths_json, default=None)
        upload_paths: list[str] = []
        if isinstance(parsed_paths, list):
            upload_paths.extend([str(p) for p in parsed_paths])
        elif path:
            upload_paths.append(path)

        if not upload_paths:
            return {"error": "file_upload requires `paths_json` or `path`."}

        try:
            locator.set_input_files(upload_paths)
            return {
                "status": "file_upload",
                "backend": "playwright",
                "page_id": effective_page_id,
                "files": upload_paths,
            }
        except Exception as e:
            return {"error": f"Failed file_upload: {e}"}

    if action_norm == "fill_form":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "fill_form requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }

        fields = _parse_json_param(fields_json, default=None)
        if fields is None and text:
            fields = _parse_json_param(text, default=None)
        if not isinstance(fields, dict):
            return {
                "error": "fill_form requires JSON object in `fields_json` or `text`.",
            }

        try:
            updated = 0
            for sel, val in fields.items():
                if not isinstance(sel, str):
                    continue
                page.locator(sel).fill(str(val))
                updated += 1
            return {
                "status": "fill_form",
                "backend": "playwright",
                "page_id": effective_page_id,
                "updated": updated,
            }
        except Exception as e:
            return {"error": f"Failed fill_form: {e}"}

    if action_norm == "install":
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "playwright", "install"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "status": "install",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            }
        except Exception as e:
            return {"error": f"Failed to install playwright: {e}"}

    if action_norm == "drag":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "drag requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }

        src = _resolve_locator(
            page_id=effective_page_id,
            page=page,
            ref=(start_ref or "") or None,
            selector=(start_selector or "") or None,
        )
        dst = _resolve_locator(
            page_id=effective_page_id,
            page=page,
            ref=(end_ref or "") or None,
            selector=(end_selector or "") or None,
        )
        if src is None or dst is None:
            return {"error": "drag requires start/end selector or ref."}
        try:
            src.drag_to(dst)
            return {
                "status": "drag",
                "backend": "playwright",
                "page_id": effective_page_id,
            }
        except Exception as e:
            return {"error": f"Failed drag: {e}"}

    if action_norm == "select_option":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "select_option requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        locator = _resolve_locator(
            page_id=effective_page_id,
            page=page,
            ref=(ref or "") or None,
            selector=(selector or "") or None,
        )
        if locator is None:
            return {"error": "select_option requires `selector` or `ref`."}

        values = _parse_json_param(values_json, default=None)
        if values is None:
            values = value or text
        try:
            result = locator.select_option(values)
            return {
                "status": "select_option",
                "backend": "playwright",
                "page_id": effective_page_id,
                "result": result,
            }
        except Exception as e:
            return {"error": f"Failed select_option: {e}"}

    if action_norm == "tabs":
        tab_action_norm = (tab_action or "list").strip().lower()
        if _BROWSER_SESSION["backend"] != "playwright":
            if tab_action_norm == "list":
                return {"status": "tabs", "backend": "http", "tabs": []}
            return {"error": "tabs action requires Playwright runtime."}

        pages = _BROWSER_SESSION.get("pages", {})
        if tab_action_norm == "list":
            return {
                "status": "tabs",
                "backend": "playwright",
                "tabs": _collect_tabs(),
            }

        if tab_action_norm == "new":
            target_page_id = effective_page_id
            if target_page_id in pages:
                idx = 2
                while f"{target_page_id}_{idx}" in pages:
                    idx += 1
                target_page_id = f"{target_page_id}_{idx}"
            page = _get_or_create_page(target_page_id, create=True)
            if page is None:
                return {"error": "Failed to create new tab."}
            if url:
                page.goto(url)
            _BROWSER_SESSION["current_page_id"] = target_page_id
            return {
                "status": "tabs",
                "backend": "playwright",
                "tab_action": "new",
                "page_id": target_page_id,
                "tabs": _collect_tabs(),
            }

        if tab_action_norm == "select":
            if index >= 0:
                keys = list(pages.keys())
                if index >= len(keys):
                    return {"error": f"Tab index out of range: {index}"}
                target_page_id = keys[index]
            else:
                target_page_id = effective_page_id
                if target_page_id not in pages:
                    return {"error": f"Unknown page_id: {target_page_id}"}
            _BROWSER_SESSION["current_page_id"] = target_page_id
            return {
                "status": "tabs",
                "backend": "playwright",
                "tab_action": "select",
                "page_id": target_page_id,
                "tabs": _collect_tabs(),
            }

        if tab_action_norm == "close":
            target_page_id = effective_page_id
            page = pages.get(target_page_id)
            if page is None:
                return {"error": f"Unknown page_id: {target_page_id}"}
            try:
                page.close()
            except Exception:
                pass
            pages.pop(target_page_id, None)
            _BROWSER_SESSION.get("refs", {}).pop(target_page_id, None)
            _BROWSER_SESSION.get("console_logs", {}).pop(target_page_id, None)
            _BROWSER_SESSION.get("network_logs", {}).pop(target_page_id, None)
            if pages:
                _BROWSER_SESSION["current_page_id"] = list(pages.keys())[0]
            return {
                "status": "tabs",
                "backend": "playwright",
                "tab_action": "close",
                "tabs": _collect_tabs(),
            }

        return {
            "error": f"Unsupported tab_action: {tab_action_norm}. Use list/new/select/close.",
        }

    if action_norm == "wait_for":
        if _BROWSER_SESSION["backend"] != "playwright":
            sec = max(wait_time, float(wait_seconds), 0.0)
            if sec > 0:
                time.sleep(sec)
            return {"status": "wait_for", "backend": "http", "seconds": sec}

        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }

        timeout_ms = int(max(wait_time * 1000, wait_seconds * 1000, 1000))
        try:
            if selector:
                page.wait_for_selector(selector, timeout=timeout_ms)
            elif ref:
                locator = _resolve_locator(effective_page_id, page, ref, None)
                if locator is None:
                    return {"error": f"Unknown ref: {ref}"}
                locator.first.wait_for(timeout=timeout_ms)
            elif text_gone:
                page.wait_for_function(
                    "txt => !document.body || !document.body.innerText.includes(txt)",
                    arg=text_gone,
                    timeout=timeout_ms,
                )
            elif text:
                page.wait_for_function(
                    "txt => document.body && document.body.innerText.includes(txt)",
                    arg=text,
                    timeout=timeout_ms,
                )
            else:
                page.wait_for_timeout(timeout_ms)
            return {
                "status": "wait_for",
                "backend": "playwright",
                "page_id": effective_page_id,
                "timeout_ms": timeout_ms,
            }
        except Exception as e:
            return {"error": f"Failed wait_for: {e}"}

    if action_norm == "pdf":
        if _BROWSER_SESSION["backend"] != "playwright":
            return {"error": "pdf requires Playwright runtime."}
        page = _get_or_create_page(effective_page_id, create=False)
        if page is None:
            return {
                "error": "No active page. Call browser_use action=open first.",
            }
        try:
            out_path = _safe_output_path(path or filename, ".pdf")
            page.pdf(path=out_path, print_background=True)
            return {
                "status": "pdf",
                "backend": "playwright",
                "page_id": effective_page_id,
                "path": out_path,
            }
        except Exception as e:
            return {"error": f"Failed pdf export: {e}"}

    if action_norm == "close":
        return browser_use(
            action="tabs",
            page_id=effective_page_id,
            tab_action="close",
        )

    if action_norm in {
        "file_upload",
        "fill_form",
        "install",
        "drag",
        "select_option",
        "tabs",
        "wait_for",
        "pdf",
        "resize",
        "console_messages",
        "network_requests",
    }:
        # handled above; this fallback is here for safety only
        return {
            "error": f"Unexpected unsupported path for action={action_norm}.",
        }

    if (
        frame_selector
        or element
        or modifiers_json
        or start_element
        or end_element
    ):
        logger.debug(
            "browser_use received optional compat fields: frame_selector=%s element=%s",
            frame_selector,
            element,
        )

    return {
        "error": (
            f"Unsupported browser_use action: {action_norm}. "
            "Supported actions: start, stop, open, navigate, navigate_back, snapshot, screenshot, "
            "click, type, fill, press, press_key, scroll, hover, eval, evaluate, run_code, "
            "resize, console_messages, network_requests, handle_dialog, file_upload, fill_form, "
            "install, drag, select_option, tabs, wait_for, pdf, close."
        ),
    }


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML."""
    import re

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
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
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
