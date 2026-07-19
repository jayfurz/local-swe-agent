"""Terminal-assistant benchmark tasks: ops work, not code editing.

Git archaeology, log analysis, file wrangling, permissions, archives,
symlinks — the other half of what a CLI agent gets asked to do. Tasks use
the Task.setup hook to build state (git history, CRLF files, archive nests)
before the agent starts. Verification stays hidden and is written post-run.
"""

from __future__ import annotations

from tasks import Task, _unittest

TERM_TASKS: list[Task] = []


def _t(**kw) -> None:
    TERM_TASKS.append(Task(**kw))


_GIT_ENV = (
    "export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null "
    "GIT_AUTHOR_NAME=bench GIT_AUTHOR_EMAIL=b@bench "
    "GIT_COMMITTER_NAME=bench GIT_COMMITTER_EMAIL=b@bench "
    "GIT_AUTHOR_DATE='2026-01-01T00:00:00 +0000' "
    "GIT_COMMITTER_DATE='2026-01-01T00:00:00 +0000'\n"
)

# --------------------------------------------------------------------------
# 1. Log analysis
# --------------------------------------------------------------------------

_t(
    id="term-log-top-ips",
    category="terminal",
    prompt=(
        "access.log is an nginx-style access log. Find the 3 client IPs (first "
        "field) with the most requests and write them to answer.txt, one per "
        "line, most frequent first, in the format: <ip> <count>"
    ),
    files={},
    setup=(
        "python3 - <<'PY'\n"
        "import random\n"
        "rng = random.Random(7)\n"
        "ips = ['10.0.0.%d' % i for i in range(1, 21)]\n"
        "weights = rng.sample(range(10, 60), 20)\n"
        "lines = []\n"
        "for ip, w in zip(ips, weights):\n"
        "    for _ in range(w):\n"
        "        lines.append(ip + ' - - [12/Mar/2026:10:00:00] \"GET /page HTTP/1.1\" 200 123')\n"
        "rng.shuffle(lines)\n"
        "open('access.log', 'w').write('\\n'.join(lines) + '\\n')\n"
        "PY\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_answer(self):\n"
            "        counts = collections.Counter(\n"
            "            line.split()[0] for line in open('access.log') if line.strip())\n"
            "        expected = [f'{ip} {n}' for ip, n in counts.most_common(3)]\n"
            "        got = [' '.join(l.split()) for l in open('answer.txt') if l.strip()]\n"
            "        self.assertEqual(got, expected)\n",
            imports="import collections\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 2. CRLF-broken script
# --------------------------------------------------------------------------

_t(
    id="term-crlf-script",
    category="terminal",
    prompt=(
        "Running ./tools/report.sh fails on this machine. Diagnose why, fix "
        "it, and run it successfully so that report.txt is produced."
    ),
    files={
        "data.csv": "item,qty\napple,3\nbread,5\ncheese,2\n",
        "tools/report.sh": (
            "#!/usr/bin/env bash\r\n"
            "set -e\r\n"
            "total=$(awk -F, 'NR>1 {s+=$2} END {print s}' data.csv)\r\n"
            'echo "TOTAL $total" > report.txt\r\n'
        ),
    },
    setup="chmod +x tools/report.sh\n",
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_fixed_and_ran(self):\n"
            "        src = open('tools/report.sh', 'rb').read()\n"
            "        self.assertNotIn(b'\\r', src, 'script still has CRLF endings')\n"
            "        self.assertEqual(open('report.txt').read().strip(), 'TOTAL 10')\n"
            "    def test_rerunnable(self):\n"
            "        r = subprocess.run(['bash', 'tools/report.sh'], capture_output=True, text=True)\n"
            "        self.assertEqual(r.returncode, 0, r.stderr)\n"
            "        self.assertEqual(open('report.txt').read().strip(), 'TOTAL 10')\n",
            imports="import subprocess\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 3. Git archaeology: find the breaking commit
# --------------------------------------------------------------------------

_t(
    id="term-git-blame-hunt",
    category="terminal",
    prompt=(
        "The tests in this repo fail. The bug was introduced by one specific "
        "commit. Use git history to identify it, write '<short-hash> "
        "<subject>' (one line) to answer.txt, and fix round_price so the tests "
        "pass (restore the correct behavior)."
    ),
    files={
        "test_pricing.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_half_cents(self):\n"
            "        self.assertEqual(round_price(2.675), 2.68)\n"
            "        self.assertEqual(round_price(1.005), 1.01)\n"
            "    def test_plain(self):\n"
            "        self.assertEqual(round_price(3.0), 3.0)\n",
            imports="from pricing import round_price\n",
        ),
    },
    setup=(
        _GIT_ENV
        + "git init -q -b main\n"
        "cat > pricing.py <<'EOF'\n"
        "def round_price(x):\n"
        "    return round(x + 1e-9, 2)\n"
        "EOF\n"
        "git add pricing.py && git commit -qm 'add pricing module'\n"
        "for i in 1 2 3; do echo \"# note $i\" >> NOTES.md; git add NOTES.md; git commit -qm \"docs: note $i\"; done\n"
        "cat > pricing.py <<'EOF'\n"
        "def round_price(x):\n"
        "    return int(x * 100) / 100\n"
        "EOF\n"
        "git add pricing.py && git commit -qm 'refactor: streamline rounding'\n"
        "for i in 4 5; do echo \"# note $i\" >> NOTES.md; git add NOTES.md; git commit -qm \"docs: note $i\"; done\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_fixed(self):\n"
            "        self.assertEqual(round_price(2.675), 2.68)\n"
            "        self.assertEqual(round_price(1.005), 1.01)\n"
            "        self.assertEqual(round_price(3.0), 3.0)\n"
            "    def test_answer_names_the_commit(self):\n"
            "        log = subprocess.run(['git', 'log', '--format=%h %s'],\n"
            "                             capture_output=True, text=True).stdout\n"
            "        expected = [l for l in log.splitlines()\n"
            "                    if l.endswith('refactor: streamline rounding')][0]\n"
            "        exp_hash = expected.split()[0]\n"
            "        line = open('answer.txt').read().strip()\n"
            "        got_hash, _, got_subject = line.partition(' ')\n"
            "        self.assertEqual(got_subject.strip(), 'refactor: streamline rounding')\n"
            "        full_exp = subprocess.run(['git', 'rev-parse', exp_hash],\n"
            "                                  capture_output=True, text=True).stdout.strip()\n"
            "        full_got = subprocess.run(['git', 'rev-parse', got_hash],\n"
            "                                  capture_output=True, text=True).stdout.strip()\n"
            "        self.assertEqual(full_got, full_exp)\n",
            imports="import subprocess\nfrom pricing import round_price\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 4. Git archaeology: restore a deleted file
# --------------------------------------------------------------------------

_t(
    id="term-restore-deleted",
    category="terminal",
    prompt=(
        "app/utils.py once existed in this repo but was deleted in a later "
        "commit. Restore the most recent version of it from git history into "
        "the working tree (no need to commit; do not rewrite or reset "
        "history), so that the provided tests pass."
    ),
    files={
        "test_slug.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_slug(self):\n"
            "        self.assertEqual(slug('Hello, World!'), 'hello-world')\n"
            "    def test_helper_restored(self):\n"
            "        self.assertEqual(unused_helper(), 42)\n",
            imports="from app.utils import slug, unused_helper\n",
        ),
    },
    setup=(
        _GIT_ENV
        + "git init -q -b main\n"
        "mkdir -p app\n"
        "cat > app/utils.py <<'EOF'\n"
        "import re\n\n\n"
        "def slug(text):\n"
        "    text = text.lower()\n"
        "    text = re.sub(r'[^a-z0-9]+', '-', text)\n"
        "    return text.strip('-')\n"
        "EOF\n"
        "echo core > app/main.py\n"
        "git add -A && git commit -qm 'initial app'\n"
        "cat >> app/utils.py <<'EOF'\n\n\n"
        "def unused_helper():\n"
        "    return 42\n"
        "EOF\n"
        "git add -A && git commit -qm 'add helper'\n"
        "git rm -q app/utils.py && git commit -qm 'remove utils (unused)'\n"
        "echo v2 >> app/main.py && git add -A && git commit -qm 'main v2'\n"
        "git rev-parse HEAD > .bench_head\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_restored_latest_version(self):\n"
            "        self.assertEqual(slug('Hello, World!'), 'hello-world')\n"
            "        self.assertEqual(slug('  A  B  '), 'a-b')\n"
            "        self.assertEqual(unused_helper(), 42)\n"
            "    def test_history_intact(self):\n"
            "        head = open('.bench_head').read().strip()\n"
            "        r = subprocess.run(['git', 'merge-base', '--is-ancestor', head, 'HEAD'])\n"
            "        self.assertEqual(r.returncode, 0, 'history was reset or rewritten')\n"
            "        main = open('app/main.py').read()\n"
            "        self.assertIn('core', main)\n"
            "        self.assertIn('v2', main)\n",
            imports="import subprocess\nfrom app.utils import slug, unused_helper\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 5. Bulk file organization
# --------------------------------------------------------------------------

_t(
    id="term-photo-rename",
    category="terminal",
    prompt=(
        "photos/ is a flat directory of files named IMG_YYYYMMDD_NNN.jpg. "
        "Reorganize it into photos/YYYY/MM/ subdirectories based on each "
        "filename's date, keeping the filenames themselves unchanged. Every "
        "file must survive the move."
    ),
    files={},
    setup=(
        "python3 - <<'PY'\n"
        "import random, pathlib\n"
        "rng = random.Random(11)\n"
        "p = pathlib.Path('photos'); p.mkdir()\n"
        "for i in range(40):\n"
        "    y = rng.choice([2023, 2024]); m = rng.randint(1, 12); d = rng.randint(1, 28)\n"
        "    (p / f'IMG_{y}{m:02d}{d:02d}_{i:03d}.jpg').write_text(f'photo {i}')\n"
        "PY\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_layout(self):\n"
            "        jpgs = list(pathlib.Path('photos').rglob('*.jpg'))\n"
            "        self.assertEqual(len(jpgs), 40, 'files were lost or duplicated')\n"
            "        for f in jpgs:\n"
            "            name = f.name\n"
            "            self.assertRegex(name, r'^IMG_\\d{8}_\\d{3}\\.jpg$')\n"
            "            y, m = name[4:8], name[8:10]\n"
            "            self.assertEqual(f.parent, pathlib.Path('photos') / y / m,\n"
            "                             f'{name} in wrong place: {f}')\n"
            "            idx = int(name[13:16])\n"
            "            self.assertEqual(f.read_text(), f'photo {idx}', 'content changed')\n",
            imports="import pathlib\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 6. Content-based dedupe
# --------------------------------------------------------------------------

_t(
    id="term-dedupe-files",
    category="terminal",
    prompt=(
        "downloads/ contains files where some are exact duplicates of each "
        "other (same content, different names). Delete the duplicates so "
        "exactly one file per unique content remains (which one you keep "
        "doesn't matter), then write the number of files you deleted to "
        "answer.txt (just the number)."
    ),
    files={},
    setup=(
        "python3 - <<'PY'\n"
        "import pathlib\n"
        "p = pathlib.Path('downloads'); p.mkdir()\n"
        "for k in range(22):\n"
        "    (p / f'file_{k:02d}.bin').write_text(f'content-{k}\\n' * (k + 1))\n"
        "for j, k in enumerate([0, 0, 3, 5, 5, 5, 11, 20]):\n"
        "    (p / f'copy_{j}.bin').write_text(f'content-{k}\\n' * (k + 1))\n"
        "PY\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_deduped(self):\n"
            "        files = list(pathlib.Path('downloads').iterdir())\n"
            "        contents = [f.read_text() for f in files]\n"
            "        expected = {f'content-{k}\\n' * (k + 1) for k in range(22)}\n"
            "        self.assertEqual(len(files), 22, 'should keep one file per unique content')\n"
            "        self.assertEqual(set(contents), expected, 'a unique content was lost')\n"
            "        self.assertEqual(open('answer.txt').read().strip(), '8')\n",
            imports="import pathlib\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 7. Nested archive needle
# --------------------------------------------------------------------------

_t(
    id="term-archive-needle",
    category="terminal",
    prompt=(
        "Somewhere inside inbox/ — archives may contain further archives — is "
        "a file with a line reading 'the token is TOKEN-…'. Find it and write "
        "just the token (starting with TOKEN-) to answer.txt."
    ),
    files={},
    setup=(
        "python3 - <<'PY'\n"
        "import io, os, tarfile, zipfile\n"
        "os.makedirs('inbox/deep', exist_ok=True)\n"
        "zbuf = io.BytesIO()\n"
        "with zipfile.ZipFile(zbuf, 'w') as z:\n"
        "    z.writestr('docs/readme.txt', 'nothing here')\n"
        "    z.writestr('docs/secret.txt', 'the token is TOKEN-7f3a9c\\n')\n"
        "with tarfile.open('inbox/deep/bundle.tar.gz', 'w:gz') as t:\n"
        "    for name, data in [('assets/a.txt', b'filler'), ('assets/inner.zip', zbuf.getvalue())]:\n"
        "        info = tarfile.TarInfo(name); info.size = len(data)\n"
        "        t.addfile(info, io.BytesIO(data))\n"
        "open('inbox/note.txt', 'w').write('nothing to see at the top level\\n')\n"
        "PY\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_token(self):\n"
            "        self.assertEqual(open('answer.txt').read().strip(), 'TOKEN-7f3a9c')\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 8. Permission repair
# --------------------------------------------------------------------------

_t(
    id="term-perms-exec",
    category="terminal",
    prompt=(
        "Permissions in this workspace are wrong: shell scripts in scripts/ "
        "are not executable, while plain data files in data/ are. Fix both: "
        "every .sh in scripts/ executable, nothing in data/ executable."
    ),
    files={},
    setup=(
        "mkdir -p scripts data\n"
        "printf '#!/bin/sh\\necho hi\\n' > scripts/run.sh\n"
        "printf '#!/bin/sh\\necho bye\\n' > scripts/stop.sh\n"
        "echo x > data/a.dat\n"
        "echo y > data/b.dat\n"
        "chmod 644 scripts/run.sh scripts/stop.sh\n"
        "chmod 755 data/a.dat data/b.dat\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_perms(self):\n"
            "        for f in pathlib.Path('scripts').glob('*.sh'):\n"
            "            self.assertTrue(os.access(f, os.X_OK), f'{f} not executable')\n"
            "        for f in pathlib.Path('data').iterdir():\n"
            "            self.assertFalse(os.access(f, os.X_OK), f'{f} still executable')\n",
            imports="import os\nimport pathlib\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 9. Broken symlink repair
# --------------------------------------------------------------------------

_t(
    id="term-broken-symlink",
    category="terminal",
    prompt=(
        "site/current is a broken symlink. Repoint it — keeping it a symlink, "
        "not a copy — at the newest existing release directory under "
        "releases/ (they are version-numbered)."
    ),
    files={},
    setup=(
        "mkdir -p releases/v1 releases/v3 site\n"
        "echo one > releases/v1/app.txt\n"
        "echo three > releases/v3/app.txt\n"
        "ln -s ../releases/v2 site/current\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_symlink(self):\n"
            "        p = pathlib.Path('site/current')\n"
            "        self.assertTrue(p.is_symlink(), 'must remain a symlink')\n"
            "        self.assertEqual(p.resolve().name, 'v3')\n"
            "        self.assertEqual((p / 'app.txt').read_text().strip(), 'three')\n"
            "        self.assertTrue(pathlib.Path('releases/v1/app.txt').exists())\n",
            imports="import pathlib\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 10. Codebase sweep with exclusion
# --------------------------------------------------------------------------

_t(
    id="term-grep-todo",
    category="terminal",
    prompt=(
        "Find every line containing 'TODO' in files under src/, excluding "
        "anything under src/vendor/. Write the matches to answer.txt as "
        "'<path>:<lineno>' (paths relative to the workspace root, 1-based "
        "line numbers), sorted lexicographically, one per line."
    ),
    files={},
    setup=(
        "python3 - <<'PY'\n"
        "import pathlib\n"
        "src = pathlib.Path('src'); (src / 'sub').mkdir(parents=True)\n"
        "(src / 'vendor').mkdir()\n"
        "def mk(path, todo_lines, n=9):\n"
        "    lines = [f'# line {i}' for i in range(1, n + 1)]\n"
        "    for ln in todo_lines:\n"
        "        lines[ln - 1] = f'# TODO: item at {ln}'\n"
        "    path.write_text('\\n'.join(lines) + '\\n')\n"
        "mk(src / 'alpha.py', [3])\n"
        "mk(src / 'beta.py', [2, 7])\n"
        "mk(src / 'gamma.py', [])\n"
        "mk(src / 'sub' / 'delta.py', [5])\n"
        "mk(src / 'sub' / 'epsilon.py', [])\n"
        "mk(src / 'vendor' / 'lib.py', [4])\n"
        "PY\n"
    ),
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_answer(self):\n"
            "        expected = []\n"
            "        for f in pathlib.Path('src').rglob('*.py'):\n"
            "            if 'vendor' in f.parts:\n"
            "                continue\n"
            "            for i, line in enumerate(f.read_text().splitlines(), 1):\n"
            "                if 'TODO' in line:\n"
            "                    expected.append(f'{f.as_posix()}:{i}')\n"
            "        expected.sort()\n"
            "        got = [l.strip() for l in open('answer.txt') if l.strip()]\n"
            "        self.assertEqual(got, expected)\n",
            imports="import pathlib\n",
        ),
    },
)


assert len(TERM_TASKS) == 10, f"expected 10 term tasks, have {len(TERM_TASKS)}"
assert len({t.id for t in TERM_TASKS}) == 10, "duplicate task ids"
