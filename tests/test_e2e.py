"""End-to-end: the full agent loop against the scripted mock server.

Verifies the whole chain — streaming chat-completions parsing, tool dispatch,
real file writes and subprocess execution in the workspace, tool-output
round-tripping into the next request, session persistence, and max-turns.
"""

import sys

import pytest
from agents import Runner, SQLiteSession
from agents.exceptions import MaxTurnsExceeded
from openai.types.responses import ResponseTextDeltaEvent

from swea.agent import build_agent
from swea.config import HarnessConfig, detect_model
from swea.tools import Workspace
from tests.mock_server import MockModelServer, ToolCall, Turn

CALC = "def add(a, b):\n    return a + b\n"
TEST_CALC = """\
import unittest
from calc import add


class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative(self):
        self.assertEqual(add(-1, 1), 0)


if __name__ == "__main__":
    unittest.main()
"""
FINAL = "Done: implemented calc.add and verified it — unittest ran 2 tests, both passed."


def _script():
    return [
        Turn(tool_calls=[
            ToolCall("write_file", {"path": "calc.py", "content": CALC}),
            ToolCall("write_file", {"path": "test_calc.py", "content": TEST_CALC}),
        ]),
        Turn(tool_calls=[ToolCall("bash", {"command": f"{sys.executable} -m unittest -v test_calc"})]),
        Turn(content=FINAL),
    ]


def _config(server, tmp_path, **kw):
    return HarnessConfig(base_url=server.base_url, model=server.model_id, workspace=tmp_path, **kw)


async def test_agent_does_real_work(tmp_path):
    with MockModelServer(_script()) as server:
        cfg = _config(server, tmp_path)
        session = SQLiteSession("e2e")
        result = Runner.run_streamed(
            build_agent(cfg),
            "Implement calc.add with tests and verify.",
            context=Workspace(cfg.workspace),
            max_turns=cfg.max_turns,
            session=session,
        )
        tool_calls, tool_outputs, text_deltas = [], [], []
        async for event in result.stream_events():
            if event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    tool_calls.append(getattr(event.item.raw_item, "name", None))
                elif event.item.type == "tool_call_output_item":
                    tool_outputs.append(str(event.item.output))
            elif event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                text_deltas.append(event.data.delta)

        # Real work happened on disk.
        assert (tmp_path / "calc.py").read_text() == CALC
        assert (tmp_path / "test_calc.py").read_text() == TEST_CALC
        # The subprocess genuinely ran the tests and they passed.
        assert tool_calls == ["write_file", "write_file", "bash"]
        bash_out = tool_outputs[-1]
        assert bash_out.startswith("exit code: 0") and "Ran 2 tests" in bash_out and "OK" in bash_out
        # Tool outputs round-tripped into the next model request.
        tool_msgs = [m for m in server.requests[-1]["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 3
        assert any("Ran 2 tests" in str(m.get("content")) for m in tool_msgs)
        # Final answer streamed and surfaced.
        assert result.final_output == FINAL
        assert "".join(text_deltas) == FINAL
        # Session recorded the conversation.
        items = await session.get_items()
        assert len(items) >= 7  # user + 2 assistant tool rounds + 3 outputs + final


async def test_max_turns_exceeded(tmp_path):
    endless = [Turn(tool_calls=[ToolCall("bash", {"command": "true"})])] * 5
    with MockModelServer(endless) as server:
        cfg = _config(server, tmp_path, max_turns=2)
        result = Runner.run_streamed(
            build_agent(cfg),
            "loop forever",
            context=Workspace(cfg.workspace),
            max_turns=cfg.max_turns,
        )
        with pytest.raises(MaxTurnsExceeded):
            async for _ in result.stream_events():
                pass


async def test_non_streamed_run_also_works(tmp_path):
    with MockModelServer(_script()) as server:
        cfg = _config(server, tmp_path)
        result = await Runner.run(
            build_agent(cfg),
            "Implement calc.add with tests and verify.",
            context=Workspace(cfg.workspace),
            max_turns=cfg.max_turns,
        )
        assert result.final_output == FINAL
        assert (tmp_path / "calc.py").exists()


def test_detect_model(tmp_path):
    with MockModelServer([]) as server:
        assert detect_model(server.base_url) == "mock-model"
