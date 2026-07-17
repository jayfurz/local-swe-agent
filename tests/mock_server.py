"""A scripted OpenAI-compatible chat-completions server.

Lets the full agent loop run with zero GPUs: each scripted ``Turn`` is either a
batch of tool calls or a final text answer. The turn to play is chosen by
counting the assistant tool-call messages already present in the request — the
SDK resends the whole conversation every round, so that count is the round
number. Supports streaming (SSE) and non-streaming responses, and records every
request body in ``.requests`` for assertions.

Also runs standalone for demos:  python tests/mock_server.py --port 8123
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class Turn:
    tool_calls: list[ToolCall] | None = None
    content: str | None = None


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output quiet
        pass

    @property
    def owner(self) -> "MockModelServer":
        return self.server.owner  # type: ignore[attr-defined]

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": self.owner.model_id, "object": "model"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json(404, {"error": "not found"})
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.owner.requests.append(body)
        rounds_done = sum(
            1 for m in body.get("messages", []) if m.get("role") == "assistant" and m.get("tool_calls")
        )
        if rounds_done < len(self.owner.script):
            turn = self.owner.script[rounds_done]
        else:
            turn = Turn(content="(mock script exhausted)")
        if body.get("stream"):
            include_usage = bool(body.get("stream_options", {}).get("include_usage"))
            self._stream_turn(turn, include_usage)
        else:
            self._complete_turn(turn)

    # -- non-streaming ------------------------------------------------------

    def _complete_turn(self, turn: Turn) -> None:
        message: dict = {"role": "assistant", "content": turn.content}
        finish = "stop"
        if turn.tool_calls:
            message["content"] = None
            message["tool_calls"] = self._tool_call_payload(turn.tool_calls)
            finish = "tool_calls"
        self._json(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 0,
                "model": self.owner.model_id,
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": _USAGE,
            },
        )

    # -- streaming ----------------------------------------------------------

    def _stream_turn(self, turn: Turn, include_usage: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        if turn.tool_calls:
            self._sse({"role": "assistant", "tool_calls": self._tool_call_payload(turn.tool_calls)})
            self._sse({}, finish_reason="tool_calls")
        else:
            content = turn.content or ""
            mid = max(len(content) // 2, 1)
            self._sse({"role": "assistant", "content": content[:mid]})
            if content[mid:]:
                self._sse({"content": content[mid:]})
            self._sse({}, finish_reason="stop")
        if include_usage:
            self._sse_raw({"id": "chatcmpl-mock", "object": "chat.completion.chunk", "created": 0,
                           "model": self.owner.model_id, "choices": [], "usage": _USAGE})
        self._chunk(b"data: [DONE]\n\n")
        self._chunk(b"")  # terminating chunk

    def _sse(self, delta: dict, finish_reason: str | None = None) -> None:
        self._sse_raw(
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": self.owner.model_id,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
            }
        )

    def _sse_raw(self, payload: dict) -> None:
        self._chunk(b"data: " + json.dumps(payload).encode() + b"\n\n")

    def _chunk(self, data: bytes) -> None:
        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def _tool_call_payload(self, tool_calls: list[ToolCall]) -> list[dict]:
        return [
            {
                "index": i,
                "id": self.owner.next_call_id(),
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for i, tc in enumerate(tool_calls)
        ]


_USAGE = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}


@dataclass
class MockModelServer:
    script: list[Turn]
    model_id: str = "mock-model"
    port: int = 0  # 0 = ephemeral
    requests: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
        self._httpd.owner = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._call_counter = 0
        self._lock = threading.Lock()

    def next_call_id(self) -> str:
        # Ids must be unique across the whole conversation, like real servers.
        with self._lock:
            self._call_counter += 1
            return f"call_{self._call_counter}"

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_port}/v1"

    def __enter__(self) -> "MockModelServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


DEMO_SCRIPT = [
    Turn(tool_calls=[
        ToolCall("write_file", {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}),
        ToolCall("write_file", {"path": "test_calc.py", "content": (
            "import unittest\n"
            "from calc import add\n\n\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n\n"
            "    def test_add_negative(self):\n"
            "        self.assertEqual(add(-1, 1), 0)\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    unittest.main()\n"
        )}),
    ]),
    Turn(tool_calls=[ToolCall("bash", {"command": "python3 -m unittest -v test_calc"})]),
    Turn(content="Done: implemented calc.add and verified it — unittest ran 2 tests, both passed."),
]


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Serve a canned coding session for demos.")
    ap.add_argument("--port", type=int, default=0, help="port to listen on (default: ephemeral)")
    ns = ap.parse_args()
    with MockModelServer(DEMO_SCRIPT, port=ns.port) as srv:
        print(f"mock model server on {srv.base_url} (Ctrl-C to stop)", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
