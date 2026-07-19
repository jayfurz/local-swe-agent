"""Prove every hard task's hidden verifier passes on a known-good solution.

A hard benchmark with a broken verifier silently punishes every model. This
materializes each task workspace, applies a reference solution, runs the
hidden verification, and fails loudly if any verifier rejects it.

    uv run python bench/selftest_hard.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tasks_hard import HARD_TASKS  # noqa: E402

REFERENCE: dict[str, dict[str, str]] = {
    "hard-lru-ttl": {
        "lruttl.py": (
            "import time\n"
            "from collections import OrderedDict\n\n\n"
            "class LRUTTLCache:\n"
            "    def __init__(self, capacity, ttl, clock=time.monotonic):\n"
            "        self.capacity, self.ttl, self.clock = capacity, ttl, clock\n"
            "        self._d = OrderedDict()\n\n"
            "    def put(self, key, value):\n"
            "        if key in self._d:\n"
            "            self._d.pop(key)\n"
            "        while len(self._d) >= self.capacity:\n"
            "            self._d.popitem(last=False)\n"
            "        self._d[key] = (value, self.clock())\n\n"
            "    def get(self, key):\n"
            "        item = self._d.get(key)\n"
            "        if item is None:\n"
            "            return None\n"
            "        value, ts = item\n"
            "        if self.clock() - ts >= self.ttl:\n"
            "            self._d.pop(key)\n"
            "            return None\n"
            "        self._d.move_to_end(key)\n"
            "        return value\n\n"
            "    def __len__(self):\n"
            "        return sum(1 for _, ts in self._d.values() if self.clock() - ts < self.ttl)\n"
        ),
    },
    "hard-interval-ops": {
        "intervals.py": (
            "def merge_intervals(pairs):\n"
            "    out = []\n"
            "    for s, e in sorted(pairs):\n"
            "        if out and s <= out[-1][1]:\n"
            "            out[-1] = (out[-1][0], max(out[-1][1], e))\n"
            "        else:\n"
            "            out.append((s, e))\n"
            "    return out\n\n\n"
            "def subtract_intervals(a, b):\n"
            "    a, b = merge_intervals(a), merge_intervals(b)\n"
            "    out = []\n"
            "    for s, e in a:\n"
            "        cur = s\n"
            "        for bs, be in b:\n"
            "            if be <= cur or bs >= e:\n"
            "                continue\n"
            "            if bs > cur:\n"
            "                out.append((cur, bs))\n"
            "            cur = max(cur, be)\n"
            "            if cur >= e:\n"
            "                break\n"
            "        if cur < e:\n"
            "            out.append((cur, e))\n"
            "    return out\n"
        ),
    },
    "hard-topo-sort": {
        "topo.py": (
            "class CycleError(Exception):\n"
            "    def __init__(self, cycle):\n"
            "        super().__init__(f'cycle: {cycle}')\n"
            "        self.cycle = cycle\n\n\n"
            "def topo_sort(graph):\n"
            "    nodes = set(graph) | {d for deps in graph.values() for d in deps}\n"
            "    color, order, stack = {}, [], []\n\n"
            "    def visit(n):\n"
            "        if color.get(n) == 2:\n"
            "            return\n"
            "        if color.get(n) == 1:\n"
            "            raise CycleError(stack[stack.index(n):])\n"
            "        color[n] = 1\n"
            "        stack.append(n)\n"
            "        for d in graph.get(n, []):\n"
            "            visit(d)\n"
            "        stack.pop()\n"
            "        color[n] = 2\n"
            "        order.append(n)\n\n"
            "    for n in sorted(nodes, key=str):\n"
            "        visit(n)\n"
            "    return order\n"
        ),
    },
    "hard-decimal-ledger": {
        "ledger.py": (
            "from decimal import Decimal\n\n\n"
            "def balances(path):\n"
            "    out = {}\n"
            "    for line in open(path):\n"
            "        line = line.strip()\n"
            "        if not line or line.startswith('#'):\n"
            "            continue\n"
            "        acct, amt = line.split()\n"
            "        neg = amt.startswith('(') and amt.endswith(')')\n"
            "        amt = amt.strip('()').lstrip('$').replace(',', '')\n"
            "        value = Decimal(amt)\n"
            "        if neg:\n"
            "            value = -value\n"
            "        out[acct] = out.get(acct, Decimal('0')) + value\n"
            "    return out\n"
        ),
    },
    "hard-state-machine": {
        "orders.py": (
            "class InvalidTransition(Exception):\n"
            "    pass\n\n\n"
            "class Order:\n"
            "    def __init__(self):\n"
            "        self.state = 'new'\n"
            "        self.refund_due = False\n"
            "        self.history = []\n\n\n"
            "def new_order():\n"
            "    return Order()\n\n\n"
            "_VALID = {\n"
            "    ('new', 'pay'): 'paid',\n"
            "    ('paid', 'ship'): 'shipped',\n"
            "    ('shipped', 'deliver'): 'delivered',\n"
            "    ('new', 'cancel'): 'cancelled',\n"
            "    ('paid', 'cancel'): 'cancelled',\n"
            "}\n\n\n"
            "def transition(order, action):\n"
            "    key = (order.state, action)\n"
            "    if key in _VALID:\n"
            "        if key == ('paid', 'cancel'):\n"
            "            order.refund_due = True\n"
            "        order.state = _VALID[key]\n"
            "    elif key == ('cancelled', 'refund') and order.refund_due:\n"
            "        order.state = 'refunded'\n"
            "    else:\n"
            "        raise InvalidTransition(f'cannot {action} from {order.state}')\n"
            "    order.history.append((action, order.state))\n"
            "    return order\n"
        ),
    },
    "hard-config-merge": {
        "cfg.py": (
            "import copy\n\n\n"
            "def merge(base, override):\n"
            "    out = copy.deepcopy(base)\n"
            "    for k, v in override.items():\n"
            "        if v is None:\n"
            "            out.pop(k, None)\n"
            "        elif isinstance(v, dict) and isinstance(out.get(k), dict):\n"
            "            out[k] = merge(out[k], v)\n"
            "        elif isinstance(v, list) and v[:1] == ['+append']:\n"
            "            out[k] = list(out.get(k, [])) + copy.deepcopy(v[1:])\n"
            "        else:\n"
            "            out[k] = copy.deepcopy(v)\n"
            "    return out\n"
        ),
    },
    "hard-diff-apply": {
        "patcher.py": (
            "import re\n\n\n"
            "class PatchError(Exception):\n"
            "    pass\n\n\n"
            "def apply_patch(text, patch):\n"
            "    lines = text.split('\\n')[:-1]\n"
            "    start, body = None, []\n"
            "    for pl in patch.split('\\n'):\n"
            "        if pl == '' or pl.startswith('---') or pl.startswith('+++'):\n"
            "            continue\n"
            "        m = re.match(r'@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@', pl)\n"
            "        if m:\n"
            "            start = int(m.group(1))\n"
            "            continue\n"
            "        body.append(pl)\n"
            "    if start is None:\n"
            "        raise PatchError('no hunk header')\n"
            "    idx = start - 1\n"
            "    out = lines[:idx]\n"
            "    for pl in body:\n"
            "        tag, content = pl[0], pl[1:]\n"
            "        if tag in ' -':\n"
            "            if idx >= len(lines) or lines[idx] != content:\n"
            "                raise PatchError(f'mismatch at line {idx + 1}')\n"
            "            if tag == ' ':\n"
            "                out.append(content)\n"
            "            idx += 1\n"
            "        elif tag == '+':\n"
            "            out.append(content)\n"
            "        else:\n"
            "            raise PatchError(f'bad patch line: {pl!r}')\n"
            "    out.extend(lines[idx:])\n"
            "    return '\\n'.join(out) + '\\n'\n"
        ),
    },
    "hard-perf-anagrams": {
        "anagrams.py": (
            "from collections import defaultdict\n\n\n"
            "def anagram_groups(words):\n"
            "    groups = defaultdict(set)\n"
            "    for w in set(words):\n"
            "        groups[''.join(sorted(w))].add(w)\n"
            "    return [sorted(g) for g in groups.values() if len(g) > 1]\n"
        ),
    },
    "hard-thread-discount": {
        "store/pricing.py": (
            "def line_total(qty, unit_price, discount=0.0):\n"
            "    return round(qty * unit_price * (1 - discount), 2)\n"
        ),
        "store/cart.py": (
            "from .pricing import line_total\n\n\n"
            "def cart_total(items, discount=0.0):\n"
            '    """items: list of (qty, unit_price) tuples."""\n'
            "    return round(sum(line_total(q, p, discount=discount) for q, p in items), 2)\n"
        ),
        "store/report.py": (
            "from .cart import cart_total\n\n\n"
            "def receipt(items, discount=0.0):\n"
            "    return f'TOTAL: {cart_total(items, discount=discount):.2f}'\n"
        ),
    },
    "hard-bug-shared-cache": {
        "settings.py": (
            "_cache = {}\n\n\n"
            "def load_settings(env):\n"
            '    """Return the settings dict for env. Cached for speed."""\n'
            "    if env not in _cache:\n"
            "        _cache[env] = _build(env)\n"
            "    return _cache[env]\n\n\n"
            "def _build(env):\n"
            "    return {'name': env, 'debug': env == 'dev'}\n"
        ),
    },
    "hard-bug-aliasing": {
        "ranking.py": (
            "def top_n(scores, n):\n"
            '    """Return the n highest scores, best first."""\n'
            "    return sorted(scores, reverse=True)[:n]\n"
        ),
    },
    "hard-refactor-extract": {
        "common.py": (
            "def split_pairs(text):\n"
            "    pairs = []\n"
            "    for part in text.split(';'):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        key, _, value = part.partition('=')\n"
            "        pairs.append((key.strip(), value.strip()))\n"
            "    return pairs\n"
        ),
        "envparse.py": (
            "from common import split_pairs\n\n\n"
            "def parse_env(text):\n"
            '    """UPPERCASE keys."""\n'
            "    return {k.upper(): v for k, v in split_pairs(text)}\n"
        ),
        "tagparse.py": (
            "from common import split_pairs\n\n\n"
            "def parse_tags(text):\n"
            '    """lowercase values."""\n'
            "    return {k: v.lower() for k, v in split_pairs(text)}\n"
        ),
        "metaparse.py": (
            "from common import split_pairs\n\n\n"
            "def parse_meta(text):\n"
            '    """Keys and values kept as-is; empty values dropped."""\n'
            "    return {k: v for k, v in split_pairs(text) if v}\n"
        ),
    },
}


def main() -> None:
    missing = {t.id for t in HARD_TASKS} - set(REFERENCE)
    assert not missing, f"no reference solution for: {missing}"
    failed = []
    for t in HARD_TASKS:
        with tempfile.TemporaryDirectory(prefix="selftest-") as td:
            ws = Path(td)
            for layer in (t.files, REFERENCE[t.id], t.verify_files):
                for rel, content in layer.items():
                    p = ws / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content)
            r = subprocess.run(t.check, shell=True, cwd=ws, capture_output=True,
                               text=True, timeout=120)
            ok = r.returncode == 0
            print(f"{t.id:26s} {'ok' if ok else 'VERIFIER FAILED'}")
            if not ok:
                failed.append(t.id)
                print((r.stdout + r.stderr)[-600:])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
