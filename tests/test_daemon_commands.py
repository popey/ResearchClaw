from pathlib import Path

from researchclaw.app.runner.daemon_commands import (
    DaemonContext,
    parse_daemon_query,
    run_daemon_logs,
    run_daemon_status,
)


def test_parse_daemon_query():
    assert parse_daemon_query("/daemon status") == ("status", [])
    assert parse_daemon_query("/restart") == ("restart", [])
    assert parse_daemon_query("/daemon logs 50") == ("logs", ["50"])
    assert parse_daemon_query("hello") is None


def test_run_daemon_logs_and_status(tmp_path: Path):
    log_file = tmp_path / "researchclaw.log"
    log_file.write_text("line1\nline2\n", encoding="utf-8")

    ctx = DaemonContext(working_dir=tmp_path)
    text = run_daemon_logs(ctx, lines=1)
    assert "line2" in text

    status = run_daemon_status(ctx)
    assert "Daemon Status" in status
