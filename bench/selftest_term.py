"""Prove every terminal task's hidden verifier passes on a reference solution.

Reference solutions here are shell commands — the ops moves a competent
terminal user would make. Each task workspace is materialized (files +
setup), the reference commands run, then the hidden verification must pass.

    uv run python bench/selftest_term.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tasks_term import TERM_TASKS  # noqa: E402

REFERENCE: dict[str, str] = {
    "term-log-top-ips": (
        "awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -3 "
        "| awk '{print $2, $1}' > answer.txt"
    ),
    "term-crlf-script": (
        "sed -i 's/\\r$//' tools/report.sh && ./tools/report.sh"
    ),
    "term-git-blame-hunt": (
        "h=$(git log --format='%h %s' | grep 'refactor: streamline rounding')\n"
        "echo \"$h\" > answer.txt\n"
        "git show $(echo $h | cut -d' ' -f1)~1:pricing.py > pricing.py\n"
    ),
    "term-restore-deleted": (
        "del=$(git log --diff-filter=D --format=%H -- app/utils.py | head -1)\n"
        "git show $del~1:app/utils.py > app/utils.py\n"
    ),
    "term-photo-rename": (
        "cd photos\n"
        "for f in IMG_*.jpg; do y=${f:4:4}; m=${f:8:2}; mkdir -p $y/$m; mv \"$f\" $y/$m/; done\n"
    ),
    "term-dedupe-files": (
        "python3 - <<'PY'\n"
        "import hashlib, pathlib\n"
        "seen, deleted = set(), 0\n"
        "for f in sorted(pathlib.Path('downloads').iterdir()):\n"
        "    h = hashlib.sha256(f.read_bytes()).hexdigest()\n"
        "    if h in seen:\n"
        "        f.unlink(); deleted += 1\n"
        "    else:\n"
        "        seen.add(h)\n"
        "open('answer.txt', 'w').write(str(deleted))\n"
        "PY\n"
    ),
    "term-archive-needle": (
        "python3 - <<'PY'\n"
        "import io, re, tarfile, zipfile\n"
        "with tarfile.open('inbox/deep/bundle.tar.gz') as t:\n"
        "    inner = t.extractfile('assets/inner.zip').read()\n"
        "with zipfile.ZipFile(io.BytesIO(inner)) as z:\n"
        "    text = z.read('docs/secret.txt').decode()\n"
        "token = re.search(r'TOKEN-\\w+', text).group(0)\n"
        "open('answer.txt', 'w').write(token + '\\n')\n"
        "PY\n"
    ),
    "term-perms-exec": (
        "chmod +x scripts/*.sh && chmod -x data/*"
    ),
    "term-broken-symlink": (
        "ln -sfn ../releases/v3 site/current"
    ),
    "term-grep-todo": (
        "grep -rn TODO src --include='*.py' | grep -v '^src/vendor/' "
        "| cut -d: -f1,2 | sort > answer.txt"
    ),
}


def main() -> None:
    missing = {t.id for t in TERM_TASKS} - set(REFERENCE)
    assert not missing, f"no reference solution for: {missing}"
    failed = []
    for t in TERM_TASKS:
        with tempfile.TemporaryDirectory(prefix="selftest-") as td:
            ws = Path(td)
            for rel, content in t.files.items():
                p = ws / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
            if t.setup:
                s = subprocess.run(t.setup, shell=True, cwd=ws, capture_output=True,
                                   text=True, timeout=60)
                if s.returncode != 0:
                    print(f"{t.id:24s} SETUP FAILED\n{(s.stdout + s.stderr)[-400:]}")
                    failed.append(t.id)
                    continue
            r = subprocess.run(REFERENCE[t.id], shell=True, cwd=ws, capture_output=True,
                               text=True, timeout=60, executable="/bin/bash")
            if r.returncode != 0:
                print(f"{t.id:24s} REFERENCE FAILED\n{(r.stdout + r.stderr)[-400:]}")
                failed.append(t.id)
                continue
            for rel, content in t.verify_files.items():
                (ws / rel).write_text(content)
            v = subprocess.run(t.check, shell=True, cwd=ws, capture_output=True,
                               text=True, timeout=120)
            ok = v.returncode == 0
            print(f"{t.id:24s} {'ok' if ok else 'VERIFIER FAILED'}")
            if not ok:
                failed.append(t.id)
                print((v.stdout + v.stderr)[-600:])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
