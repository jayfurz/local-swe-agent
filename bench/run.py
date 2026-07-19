"""Benchmark runner: drive swea through the 30 tasks against one model.

Usage:
    uv run python bench/run.py --base-url http://localhost:11434/v1 --model qwen36-bench

For each task: fresh workspace -> run swea one-shot -> write the hidden
verification files (clobbering any tampering) -> run the check -> record.
Sequential on purpose: one local GPU, one model instance.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tasks import TASKS  # noqa: E402
from tasks_hard import HARD_TASKS  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def _opencode_config(args) -> str:
    return json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "model": f"local/{args.model}",
        "small_model": f"local/{args.model}",
        "provider": {
            "local": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "bench endpoint",
                "options": {"baseURL": args.base_url, "apiKey": "bench"},
                "models": {
                    args.model: {
                        "name": args.model,
                        "tool_call": True,
                        "temperature": True,
                        "limit": {"context": 32768, "output": 8192},
                    }
                },
            }
        },
        "permission": {"*": "allow"},
    })


def build_invocation(task, args, ws: Path):
    """Return (cmd, cwd, env) for the chosen harness."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    env["NO_COLOR"] = "1"
    if args.harness == "swea":
        cmd = [
            sys.executable, "-m", "swea.cli",
            "--base-url", args.base_url,
            "--model", args.model,
            "--max-turns", str(args.max_turns),
            "--temperature", str(args.temperature),
            "--workspace", str(ws),
            task.prompt,
        ]
        return cmd, REPO, env
    if args.harness == "opencode":
        (ws / "opencode.json").write_text(_opencode_config(args))
        cmd = ["opencode", "run", task.prompt,
               "-m", f"local/{args.model}", "--dangerously-skip-permissions"]
        # subprocess cwd= does not update $PWD; opencode trusts $PWD for
        # project detection and crashes (or picks the wrong dir) on mismatch.
        env["PWD"] = str(ws)
        env.pop("OLDPWD", None)
        return cmd, ws, env
    if args.harness == "claude":
        # Same controlled endpoint: ollama's Anthropic-compatible /v1/messages.
        anthropic_base = args.base_url.removesuffix("/v1")
        env.update(
            ANTHROPIC_BASE_URL=anthropic_base,
            ANTHROPIC_AUTH_TOKEN="bench",
            ANTHROPIC_SMALL_FAST_MODEL=args.model,
            CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
            DISABLE_TELEMETRY="1",
            DISABLE_ERROR_REPORTING="1",
            DISABLE_AUTOUPDATER="1",
        )
        cmd = ["claude", "-p", task.prompt, "--model", args.model,
               "--dangerously-skip-permissions", "--output-format", "json",
               "--strict-mcp-config"]
        env["PWD"] = str(ws)
        env.pop("OLDPWD", None)
        return cmd, ws, env
    raise SystemExit(f"unknown harness {args.harness}")


def run_one(task, args, workdir: Path) -> dict:
    ws = workdir / task.id
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for rel, content in task.files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    cmd, cwd, env = build_invocation(task, args, ws)
    t0 = time.monotonic()
    status = "ok"
    stdout = ""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=args.task_timeout,
            env=env, cwd=cwd,
        )
        stdout = proc.stdout + proc.stderr
        if args.harness == "swea" and proc.returncode == 2:
            status = "max_turns"
        elif proc.returncode != 0:
            status = "agent_error"
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        stdout = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
    agent_seconds = time.monotonic() - t0

    for rel, content in task.verify_files.items():
        (ws / rel).write_text(content)
    try:
        check = subprocess.run(
            task.check, shell=True, cwd=ws, capture_output=True, text=True, timeout=60,
        )
        passed = check.returncode == 0
        check_out = (check.stdout + check.stderr)[-400:]
    except subprocess.TimeoutExpired:
        passed = False
        check_out = "(verification timed out)"

    tool_calls = len(re.findall(r"^▶ (\w+)", stdout, re.M)) or None
    turns = None
    if args.harness == "claude":
        m = re.search(r'"num_turns"\s*:\s*(\d+)', stdout)
        turns = int(m.group(1)) if m else None
        if re.search(r'"is_error"\s*:\s*true', stdout):
            status = "agent_error"
    return {
        "task": task.id,
        "category": task.category,
        "passed": passed,
        "status": status,
        "seconds": round(agent_seconds, 1),
        "tool_calls": tool_calls,
        "turns": turns,
        "check_output": check_out if not passed else "",
        "agent_tail": stdout[-500:] if not passed else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harness", choices=["swea", "opencode", "claude"], default="swea")
    ap.add_argument("--suite", choices=["core", "hard", "all"], default="core")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--task-timeout", type=int, default=300)
    ap.add_argument("--only", help="comma-separated task ids")
    ap.add_argument("--out", help="results JSON path")
    ap.add_argument("--workdir", help="where task workspaces live (default: temp dir)")
    args = ap.parse_args()

    pool = {"core": TASKS, "hard": HARD_TASKS, "all": TASKS + HARD_TASKS}[args.suite]
    if args.only:
        by_id = {t.id: t for t in pool}
        tasks = [by_id[i] for i in args.only.split(",")]
    else:
        tasks = list(pool)
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="swea-bench-"))
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    results = []
    for i, task in enumerate(tasks, 1):
        r = run_one(task, args, workdir)
        results.append(r)
        mark = "PASS" if r["passed"] else f"FAIL({r['status']})"
        effort = f"{r['tool_calls']} tool calls" if r["tool_calls"] else (
            f"{r['turns']} turns" if r["turns"] else "")
        print(f"[{i:2}/{len(tasks)}] {task.id:24s} {mark:16s} {r['seconds']:6.1f}s  {effort}", flush=True)

    by_cat: dict[str, list[dict]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)
    print("\n== summary ==")
    for cat, rs in sorted(by_cat.items()):
        n = sum(r["passed"] for r in rs)
        print(f"  {cat:10s} {n}/{len(rs)}")
    total = sum(r["passed"] for r in results)
    secs = sum(r["seconds"] for r in results)
    print(f"  {'TOTAL':10s} {total}/{len(results)}  ({100 * total / len(results):.0f}%)  wall {secs/60:.1f} min")

    payload = {
        "harness": args.harness,
        "suite": args.suite,
        "model": args.model,
        "base_url": args.base_url,
        "max_turns": args.max_turns,
        "task_timeout": args.task_timeout,
        "started_at": started,
        "total_passed": total,
        "total_tasks": len(results),
        "results": results,
    }
    out = Path(args.out) if args.out else REPO / "bench" / "results" / (
        args.suite + "-" + args.harness + "-" + re.sub(r"[^A-Za-z0-9._-]+", "_", args.model)
        + "-" + started.replace(":", "") + ".json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"results -> {out}")


if __name__ == "__main__":
    main()
