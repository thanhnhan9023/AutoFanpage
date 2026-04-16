import json

import pytest

from autofanpage.mcp import MCPClient, MCPError


def test_call_tool_invokes_openclaw_mcp_cli(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": True, "result": {"notebook_id": "nb_123"}})
    fake.stderr = ""
    run = mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    out = client.call_tool(
        server="notebooklm-mcp",
        tool="notebook_create",
        args={"title": "AI Research 2026-04-15"},
    )
    assert out == {"notebook_id": "nb_123"}

    cmd = run.call_args.args[0]
    assert cmd[0] == "openclaw"
    assert cmd[1] == "mcp"
    assert cmd[2] == "call"
    assert cmd[3] == "notebooklm-mcp"
    assert cmd[4] == "notebook_create"
    assert "--args-json" in cmd
    args_idx = cmd.index("--args-json") + 1
    assert json.loads(cmd[args_idx]) == {"title": "AI Research 2026-04-15"}


def test_call_tool_raises_on_nonzero_exit(mocker):
    fake = mocker.Mock()
    fake.returncode = 1
    fake.stdout = ""
    fake.stderr = "auth error: cookies expired"
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError) as exc:
        client.call_tool(server="notebooklm-mcp", tool="notebook_create", args={})
    assert "cookies expired" in str(exc.value)


def test_call_tool_raises_on_malformed_json(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = "not json at all"
    fake.stderr = ""
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError):
        client.call_tool(server="notebooklm-mcp", tool="notebook_query", args={})


def test_call_tool_raises_on_ok_false(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": False, "error": "rate limit"})
    fake.stderr = ""
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError) as exc:
        client.call_tool(server="notebooklm-mcp", tool="notebook_query", args={})
    assert "rate limit" in str(exc.value)


def test_timeout_is_passed_to_subprocess(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": True, "result": {}})
    fake.stderr = ""
    run = mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    MCPClient().call_tool(
        server="s", tool="t", args={}, timeout=42,
    )
    assert run.call_args.kwargs["timeout"] == 42
