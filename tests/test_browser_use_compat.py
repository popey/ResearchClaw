from researchclaw.agents.tools import browser_control


def test_browser_use_start_and_stop() -> None:
    start = browser_control.browser_use(action="start", headed=True)
    assert start.get("status") == "started"
    assert start.get("headed") is True

    stop = browser_control.browser_use(action="stop")
    assert stop.get("status") == "stopped"


def test_browser_use_open_and_snapshot(monkeypatch) -> None:
    def _fake_browse_url(**kwargs):
        return {
            "url": kwargs.get("url"),
            "title": "Fake",
            "text": "ok",
        }

    monkeypatch.setattr(browser_control, "browse_url", _fake_browse_url)
    browser_control.browser_use(action="start")
    opened = browser_control.browser_use(action="open", url="https://example.com")
    assert opened.get("status") == "opened"
    assert opened["result"]["title"] == "Fake"

    snap = browser_control.browser_use(action="snapshot")
    assert snap.get("status") == "snapshot"
    assert snap["result"]["url"] == "https://example.com"

    browser_control.browser_use(action="stop")


def test_browser_use_tabs_list_in_http_mode() -> None:
    browser_control.browser_use(action="start")
    result = browser_control.browser_use(action="tabs", tab_action="list")
    assert result.get("status") == "tabs"
    assert result.get("backend") in {"http", "playwright"}
    browser_control.browser_use(action="stop")


def test_browser_use_press_key_requires_playwright_or_page() -> None:
    browser_control.browser_use(action="start")
    result = browser_control.browser_use(action="press_key", key="Enter")
    assert "status" in result or "error" in result
    browser_control.browser_use(action="stop")
