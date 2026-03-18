from researchclaw.agents.skills.arxiv.tools import _looks_like_rate_limit_error
from researchclaw.agents.tools.semantic_scholar import _retry_after_seconds


def test_arxiv_rate_limit_detection() -> None:
    assert _looks_like_rate_limit_error(Exception("HTTP 429")) is True
    assert _looks_like_rate_limit_error(Exception("Too many requests")) is True
    assert (
        _looks_like_rate_limit_error(Exception("connection timeout")) is False
    )


def test_retry_after_seconds_parsing() -> None:
    assert _retry_after_seconds(None) == 0.0
    assert _retry_after_seconds("") == 0.0
    assert _retry_after_seconds("2.5") == 2.5
    assert _retry_after_seconds("abc") == 0.0
