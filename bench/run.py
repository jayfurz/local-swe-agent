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
from tasks import get_tasks  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def run_one(task, args, workdir: Path) -> dict:
    ws = workdir / task.id
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for rel, content in task.files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    cmd = [
        sys.executable, "-m", "swea.cli",
        "--base-url", args.base_url,
        "--model", args.model,
        "--max-turns", str(args.max_turns),
        "--temperature", str(args.temperature),
        "--workspace", str(ws),
        task.prompt,
    ]
    env = dict(os.environ, NO_COLOR="1")
    t0 = time.monotonic()
    status = "ok"
    stdout = ""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=args.task_timeout,
            env=env, cwd=REPO,
        )
        stdout = proc.stdout + proc.stderr
        if proc.returncode == 2:
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

    tool_calls = len(re.findall(r"^▶ (\w+)", stdout, re.M))
    return {
        "task": task.id,
        "category": task.category,
        "passed": passed,
        "status": status,
        "seconds": round(agent_seconds, 1),
        "tool_calls": tool_calls,
        "check_output": check_out if not passed else "",
        "agent_tail": stdout[-500:] if not passed else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--task-timeout", type=int, default=300)
    ap.add_argument("--only", help="comma-separated task ids")
    ap.add_argument("--out", help="results JSON path")
    ap.add_argument("--workdir", help="where task workspaces live (default: temp dir)")
    args = ap.parse_args()

    tasks = get_tasks(args.only.split(",") if args.only else None)
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="swea-bench-"))
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    results = []
    for i, task in enumerate(tasks, 1):
        r = run_one(task, args, workdir)
        results.append(r)
        mark = "PASS" if r["passed"] else f"FAIL({r['status']})"
        print(f"[{i:2}/{len(tasks)}] {task.id:24s} {mark:16s} {r['seconds']:6.1f}s  {r['tool_calls']} tool calls", flush=True)

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
        re.sub(r"[^A-Za-z0-9._-]+", "_", args.model) + "-" + started.replace(":", "") + ".json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"results -> {out}")


if __name__ == "__main__":
    main()
