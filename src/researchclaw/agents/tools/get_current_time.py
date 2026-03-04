"""Get current time tool."""

from __future__ import annotations

from datetime import datetime, timezone


def get_current_time(
    timezone_name: str = "UTC",
    format_str: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str:
    """Get the current date and time.

    Parameters
    ----------
    timezone_name:
        Timezone name (default ``"UTC"``). Common values:
        ``"UTC"``, ``"US/Eastern"``, ``"Asia/Shanghai"``, ``"Europe/London"``.
    format_str:
        strftime format string.

    Returns
    -------
    str
        Formatted current time string.
    """
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(timezone_name)
    except (ImportError, KeyError):
        tz = timezone.utc

    now = datetime.now(tz)
    return now.strftime(format_str)
