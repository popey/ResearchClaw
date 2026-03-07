from researchclaw.agents.tools import copaw_compat


def test_execute_shell_command_alias_success(monkeypatch) -> None:
    def _fake_run_shell(**kwargs):
        assert kwargs["command"] == "echo ok"
        return {"stdout": "ok", "stderr": "", "returncode": 0}

    monkeypatch.setattr(copaw_compat, "run_shell", _fake_run_shell)
    out = copaw_compat.execute_shell_command("echo ok")
    assert out == "ok"


def test_execute_shell_command_alias_error(monkeypatch) -> None:
    def _fake_run_shell(**kwargs):
        return {"stdout": "", "stderr": "boom", "returncode": 2}

    monkeypatch.setattr(copaw_compat, "run_shell", _fake_run_shell)
    out = copaw_compat.execute_shell_command("bad")
    assert "exit code 2" in out
    assert "[stderr]" in out


def test_send_file_to_user_alias(monkeypatch) -> None:
    expected = {"type": "file"}

    def _fake_send_file(*, file_path: str):
        assert file_path == "/tmp/a.txt"
        return expected

    monkeypatch.setattr(copaw_compat, "send_file", _fake_send_file)
    out = copaw_compat.send_file_to_user("/tmp/a.txt")
    assert out is expected
