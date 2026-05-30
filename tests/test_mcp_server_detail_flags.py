import asyncio
import importlib
import json
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path

import pytest  # type: ignore[reportMissingImports]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class _FakeServer:
    def __init__(self, name: str):
        self.name = name

    def list_tools(self):
        return lambda fn: fn

    def call_tool(self):
        return lambda fn: fn

    def create_initialization_options(self):
        return {}

    async def run(self, *_args, **_kwargs):  # pragma: no cover - startup path only
        return None


@asynccontextmanager
async def _fake_stdio_server():
    yield (None, None)


class _FakeTool:
    def __init__(self, *, name: str, description: str, inputSchema: dict):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema


class _FakeTextContent:
    def __init__(self, *, type: str, text: str):
        self.type = type
        self.text = text


@pytest.fixture()
def mcp_server_module(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    sessions_dir = state_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    (state_dir / "projects.json").write_text("[]", encoding="utf-8")
    (sessions_dir / "_index.json").write_text("[]", encoding="utf-8")

    monkeypatch.setenv("HERMES_WEBUI_STATE_DIR", str(state_dir))
    monkeypatch.setattr(sys, "argv", ["mcp_server.py"])

    mcp_pkg = types.ModuleType("mcp")
    mcp_server_pkg = types.ModuleType("mcp.server")
    setattr(mcp_server_pkg, "Server", _FakeServer)
    mcp_server_stdio_pkg = types.ModuleType("mcp.server.stdio")
    setattr(mcp_server_stdio_pkg, "stdio_server", _fake_stdio_server)
    mcp_types_pkg = types.ModuleType("mcp.types")
    setattr(mcp_types_pkg, "Tool", _FakeTool)
    setattr(mcp_types_pkg, "TextContent", _FakeTextContent)

    monkeypatch.setitem(sys.modules, "mcp", mcp_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server.stdio", mcp_server_stdio_pkg)
    monkeypatch.setitem(sys.modules, "mcp.types", mcp_types_pkg)

    for name in ("mcp_server", "api.config", "api.models", "api.profiles"):
        sys.modules.pop(name, None)

    return importlib.import_module("mcp_server")


def _seed_session(mod, session_id: str, *, title: str, messages: list[dict], project_id=None) -> None:
    session_path = mod.SESSION_DIR / f"{session_id}.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "title": title,
                "project_id": project_id,
                "messages": messages,
            }
        ),
        encoding="utf-8",
    )



def _write_index(mod, rows: list[dict]) -> None:
    mod.SESSION_INDEX_FILE.write_text(json.dumps(rows), encoding="utf-8")


def _decode_text_payload(result) -> list[dict]:
    assert len(result) == 1
    return json.loads(result[0].text)


def test_list_sessions_detail_string_false_stays_compact(mcp_server_module):
    mod = mcp_server_module
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    _seed_session(mod, "detail_string_false", title="Detail False", messages=messages)
    _write_index(
        mod,
        [
            {
                "session_id": "detail_string_false",
                "title": "Detail False",
                "project_id": None,
                "profile": "default",
            }
        ],
    )

    payload = _decode_text_payload(asyncio.run(mod.handle_list_sessions({"detail": "false"})))

    assert len(payload) == 1
    assert payload[0]["session_id"] == "detail_string_false"
    assert "messages" not in payload[0]


def test_list_sessions_detail_string_true_accepts_nested_quotes(mcp_server_module):
    mod = mcp_server_module
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    _seed_session(mod, "detail_string_true", title="Detail True", messages=messages)
    _write_index(
        mod,
        [
            {
                "session_id": "detail_string_true",
                "title": "Detail True",
                "project_id": None,
                "profile": "default",
            }
        ],
    )

    payload = _decode_text_payload(asyncio.run(mod.handle_list_sessions({"detail": '\'"true"\''})))

    assert len(payload) == 1
    assert payload[0]["session_id"] == "detail_string_true"
    assert payload[0]["messages"] == messages


def test_list_sessions_unassigned_string_flags_are_coerced(mcp_server_module):
    mod = mcp_server_module
    messages = [{"role": "user", "content": "Hello"}]
    _seed_session(mod, "assigned_session", title="Assigned", messages=messages, project_id="proj_1")
    _seed_session(mod, "unassigned_session", title="Unassigned", messages=messages, project_id=None)
    _write_index(
        mod,
        [
            {
                "session_id": "assigned_session",
                "title": "Assigned",
                "project_id": "proj_1",
                "profile": "default",
            },
            {
                "session_id": "unassigned_session",
                "title": "Unassigned",
                "project_id": None,
                "profile": "default",
            },
        ],
    )

    all_sessions = _decode_text_payload(asyncio.run(mod.handle_list_sessions({"unassigned": "false"})))
    unassigned_only = _decode_text_payload(asyncio.run(mod.handle_list_sessions({"unassigned": "true"})))

    assert {row["session_id"] for row in all_sessions} == {"assigned_session", "unassigned_session"}
    assert [row["session_id"] for row in unassigned_only] == ["unassigned_session"]


def test_list_sessions_schema_allows_boolean_or_string_flags(mcp_server_module):
    mod = mcp_server_module
    tool = next(tool for tool in mod.TOOLS if tool.name == "list_sessions")

    detail_types = {branch["type"] for branch in tool.inputSchema["properties"]["detail"]["anyOf"]}
    unassigned_types = {branch["type"] for branch in tool.inputSchema["properties"]["unassigned"]["anyOf"]}

    assert detail_types == {"boolean", "string"}
    assert unassigned_types == {"boolean", "string"}
