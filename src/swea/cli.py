"""swea command-line interface: one-shot tasks and an interactive REPL."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import urllib.error
from pathlib import Path

import openai
from agents import Runner, SQLiteSession
from agents.exceptions import MaxTurnsExceeded
from openai.types.responses import ResponseTextDeltaEvent

from . import __version__
from .agent import build_agent
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_TURNS,
    DEFAULT_TEMPERATURE,
    HarnessConfig,
    detect_model,
)
from .tools import Workspace

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def _one_line(text: str, limit: int = 160) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _preview(text: str, limit: int = 400) -> str:
    clipped = text if len(text) <= limit else text[: limit - 1] + "…"
    return "\n".join("  │ " + line for line in clipped.splitlines() or [""])


async def _run_task(agent, task: str, cfg: HarnessConfig, session) -> None:
    result = Runner.run_streamed(
        agent,
        task,
        context=Workspace(cfg.workspace),
        max_turns=cfg.max_turns,
        session=session,
    )
    mid_text = False
    async for event in result.stream_events():
        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)
                mid_text = True
        elif event.type == "run_item_stream_event":
            item = event.item
            if item.type == "tool_call_item":
                if mid_text:
                    print()
                    mid_text = False
                name = getattr(item.raw_item, "name", "?")
                args = getattr(item.raw_item, "arguments", "") or ""
                print(_c("36", f"▶ {name}") + " " + _c("2", _one_line(args)))
            elif item.type == "tool_call_output_item":
                print(_c("2", _preview(str(item.output))))
    if mid_text:
        print()


async def _amain(cfg: HarnessConfig, task: str | None, session) -> int:
    agent = build_agent(cfg)
    try:
        if task is not None:
            await _run_task(agent, task, cfg, session)
            return 0
        print(_c("2", "interactive mode — empty line or Ctrl-D to exit"))
        while True:
            try:
                line = await asyncio.to_thread(input, _c("1", "swea> "))
            except EOFError:
                return 0
            if not line.strip():
                return 0
            await _run_task(agent, line, cfg, session)
    except MaxTurnsExceeded:
        print(f"\nswea: stopped after {cfg.max_turns} turns (raise with --max-turns)", file=sys.stderr)
        return 2
    except openai.APIConnectionError:
        print(f"\nswea: cannot reach the model server at {cfg.base_url} — is it running?", file=sys.stderr)
        return 1
    except openai.APIStatusError as e:
        detail = e.message if isinstance(e.message, str) else e.body
        print(f"\nswea: the server rejected the request (HTTP {e.status_code}): {detail}", file=sys.stderr)
        return 1


def _make_session(args: argparse.Namespace) -> SQLiteSession:
    name = args.session or ("default" if args.cont else None)
    if name is None:
        return SQLiteSession("adhoc")  # in-memory: multi-turn within this process only
    data_dir = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "swea"
    data_dir.mkdir(parents=True, exist_ok=True)
    return SQLiteSession(name, str(data_dir / "sessions.db"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="swea",
        description="Coding agent for local OpenAI-compatible models. "
        "Run with a task for one-shot mode, or without for a REPL.",
    )
    parser.add_argument("task", nargs="?", help="task to perform (omit for interactive mode)")
    parser.add_argument("--base-url", default=None, help=f"OpenAI-compatible base URL (default: $SWEA_BASE_URL, $OPENAI_BASE_URL, or {DEFAULT_BASE_URL})")
    parser.add_argument("--model", default=None, help="model id (default: $SWEA_MODEL, or auto-detect from the server)")
    parser.add_argument("--api-key", default=None, help="API key (default: $SWEA_API_KEY, $OPENAI_API_KEY, or 'local')")
    parser.add_argument("--workspace", default=".", help="workspace root the agent works in (default: cwd)")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, help=f"max agent loop turns per task (default: {DEFAULT_MAX_TURNS})")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help=f"sampling temperature (default: {DEFAULT_TEMPERATURE})")
    parser.add_argument("--session", default=None, metavar="NAME", help="persist conversation under NAME (~/.local/share/swea/sessions.db)")
    parser.add_argument("--continue", dest="cont", action="store_true", help="continue the previous session (implies --session default)")
    parser.add_argument("--version", action="version", version=f"swea {__version__}")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        parser.error(f"workspace {workspace} is not a directory")

    base_url = args.base_url or os.environ.get("SWEA_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    api_key = args.api_key or os.environ.get("SWEA_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local"
    model = args.model or os.environ.get("SWEA_MODEL")
    if model is None:
        try:
            model = detect_model(base_url, api_key)
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as e:
            sys.exit(f"swea: cannot auto-detect a model from {base_url} ({e}); pass --model, or start the server")

    cfg = HarnessConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        workspace=workspace,
        max_turns=args.max_turns,
        temperature=args.temperature,
    )
    print(_c("2", f"swea · model={cfg.model} · base={cfg.base_url} · workspace={cfg.workspace}"))
    try:
        raise SystemExit(asyncio.run(_amain(cfg, args.task, _make_session(args))))
    except KeyboardInterrupt:
        print("\nswea: interrupted", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
