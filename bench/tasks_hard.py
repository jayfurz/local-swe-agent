"""Hard-tier benchmark tasks: designed to discriminate, not to saturate.

Same contract as tasks.py (visible files + prompt; hidden verify_files
written post-run). Difficulty comes from: multi-file consistency, bugs far
from their symptoms, exact-arithmetic traps, performance gates, spec tables,
and refactors with structural checks.
"""

from __future__ import annotations

from tasks import Task, _unittest

HARD_TASKS: list[Task] = []


def _t(**kw) -> None:
    HARD_TASKS.append(Task(**kw))


# --------------------------------------------------------------------------
# 1. LRU cache with TTL and injectable clock
# --------------------------------------------------------------------------

_t(
    id="hard-lru-ttl",
    category="hard-impl",
    prompt=(
        "Implement LRUTTLCache in lruttl.py:\n"
        "- LRUTTLCache(capacity, ttl, clock=time.monotonic): capacity > 0; ttl in "
        "seconds; clock is a zero-arg callable returning the current time.\n"
        "- put(key, value): insert or update; updating resets both the entry's "
        "recency and its expiry timestamp. If inserting would exceed capacity, "
        "evict the least-recently-used entry first.\n"
        "- get(key): return the value, or None if the key is absent or expired. "
        "A hit refreshes the entry's recency but NOT its expiry timestamp.\n"
        "- An entry expires once (now - written_at) >= ttl. Expired entries "
        "behave as absent.\n"
        "- len(cache) returns the number of non-expired entries.\n"
        "Run the provided tests to verify."
    ),
    files={
        "lruttl.py": "import time\n\n\nclass LRUTTLCache:\n    pass  # TODO\n",
        "test_lruttl.py": _unittest(
            "class FakeClock:\n"
            "    def __init__(self):\n"
            "        self.t = 0.0\n"
            "    def __call__(self):\n"
            "        return self.t\n\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_basic_lru(self):\n"
            "        c = FakeClock()\n"
            "        cache = LRUTTLCache(2, ttl=100, clock=c)\n"
            "        cache.put('a', 1)\n"
            "        cache.put('b', 2)\n"
            "        cache.get('a')\n"
            "        cache.put('x', 3)  # evicts b, not a\n"
            "        self.assertIsNone(cache.get('b'))\n"
            "        self.assertEqual(cache.get('a'), 1)\n"
            "    def test_ttl(self):\n"
            "        c = FakeClock()\n"
            "        cache = LRUTTLCache(2, ttl=10, clock=c)\n"
            "        cache.put('a', 1)\n"
            "        c.t = 11\n"
            "        self.assertIsNone(cache.get('a'))\n",
            imports="from lruttl import LRUTTLCache\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class FakeClock:\n"
            "    def __init__(self):\n"
            "        self.t = 0.0\n"
            "    def __call__(self):\n"
            "        return self.t\n\n\n"
            "class V(unittest.TestCase):\n"
            "    def test_trace(self):\n"
            "        c = FakeClock()\n"
            "        cache = LRUTTLCache(2, ttl=10, clock=c)\n"
            "        cache.put('a', 1)          # t=0\n"
            "        c.t = 5\n"
            "        cache.put('b', 2)\n"
            "        self.assertEqual(cache.get('a'), 1)   # refresh recency only\n"
            "        c.t = 6\n"
            "        cache.put('x', 3)          # evict LRU = b\n"
            "        self.assertIsNone(cache.get('b'))\n"
            "        self.assertEqual(cache.get('a'), 1)\n"
            "        c.t = 11                   # a written at t=0 -> expired\n"
            "        self.assertIsNone(cache.get('a'))\n"
            "        self.assertEqual(cache.get('x'), 3)\n"
            "        self.assertEqual(len(cache), 1)\n"
            "    def test_put_resets_ttl(self):\n"
            "        c = FakeClock()\n"
            "        cache = LRUTTLCache(2, ttl=10, clock=c)\n"
            "        cache.put('a', 1)\n"
            "        c.t = 8\n"
            "        cache.put('a', 2)          # rewrite resets expiry\n"
            "        c.t = 15\n"
            "        self.assertEqual(cache.get('a'), 2)\n",
            imports="from lruttl import LRUTTLCache\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 2. Interval algebra with half-open semantics
# --------------------------------------------------------------------------

_t(
    id="hard-interval-ops",
    category="hard-impl",
    prompt=(
        "Implement intervals.py with half-open [start, end) integer intervals:\n"
        "- merge_intervals(pairs): normalize any list of (start, end) tuples into "
        "a sorted list of disjoint intervals; adjacent intervals like (1,3),(3,5) "
        "merge into (1,5).\n"
        "- subtract_intervals(a, b): the normalized parts of a not covered by b.\n"
        "Both return lists of tuples. Run the provided tests to verify."
    ),
    files={
        "intervals.py": (
            "def merge_intervals(pairs):\n    raise NotImplementedError\n\n\n"
            "def subtract_intervals(a, b):\n    raise NotImplementedError\n"
        ),
        "test_intervals.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_merge(self):\n"
            "        self.assertEqual(merge_intervals([(5, 7), (1, 3), (3, 5)]), [(1, 7)])\n"
            "    def test_subtract(self):\n"
            "        self.assertEqual(subtract_intervals([(1, 10)], [(2, 3), (5, 7)]),\n"
            "                         [(1, 2), (3, 5), (7, 10)])\n",
            imports="from intervals import merge_intervals, subtract_intervals\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_merge_adjacent_and_overlap(self):\n"
            "        self.assertEqual(merge_intervals([(5, 7), (1, 3), (3, 5)]), [(1, 7)])\n"
            "        self.assertEqual(merge_intervals([(1, 2), (4, 5)]), [(1, 2), (4, 5)])\n"
            "        self.assertEqual(merge_intervals([]), [])\n"
            "    def test_subtract_spanning(self):\n"
            "        self.assertEqual(subtract_intervals([(1, 5), (7, 9)], [(4, 8)]),\n"
            "                         [(1, 4), (8, 9)])\n"
            "    def test_subtract_everything(self):\n"
            "        self.assertEqual(subtract_intervals([(1, 5)], [(0, 10)]), [])\n"
            "    def test_subtract_nothing(self):\n"
            "        self.assertEqual(subtract_intervals([(3, 4), (1, 2)], []),\n"
            "                         [(1, 2), (3, 4)])\n",
            imports="from intervals import merge_intervals, subtract_intervals\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 3. Topological sort with cycle reporting
# --------------------------------------------------------------------------

_t(
    id="hard-topo-sort",
    category="hard-impl",
    prompt=(
        "Implement topo.py:\n"
        "- topo_sort(graph): graph maps node -> list of dependency nodes (deps "
        "must come before the node). Return a list containing every node exactly "
        "once, with each node appearing after all of its dependencies. Any valid "
        "order is accepted.\n"
        "- On a cycle, raise CycleError (define it in topo.py) with a `cycle` "
        "attribute holding the nodes of one cycle (any order, at least 2 nodes).\n"
        "Nodes referenced only as dependencies also appear in the result. Run "
        "the provided tests to verify."
    ),
    files={
        "topo.py": (
            "class CycleError(Exception):\n    pass\n\n\n"
            "def topo_sort(graph):\n    raise NotImplementedError\n"
        ),
        "test_topo.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_chain(self):\n"
            "        order = topo_sort({'a': ['b'], 'b': ['c'], 'c': []})\n"
            "        self.assertLess(order.index('c'), order.index('b'))\n"
            "        self.assertLess(order.index('b'), order.index('a'))\n"
            "    def test_cycle(self):\n"
            "        with self.assertRaises(CycleError):\n"
            "            topo_sort({'a': ['b'], 'b': ['a']})\n",
            imports="from topo import topo_sort, CycleError\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "def check(graph):\n"
            "    order = topo_sort(graph)\n"
            "    nodes = set(graph) | {d for deps in graph.values() for d in deps}\n"
            "    assert sorted(order) == sorted(nodes), 'each node exactly once'\n"
            "    pos = {n: i for i, n in enumerate(order)}\n"
            "    for n, deps in graph.items():\n"
            "        for d in deps:\n"
            "            assert pos[d] < pos[n], f'{d} must precede {n}'\n\n\n"
            "class V(unittest.TestCase):\n"
            "    def test_diamond(self):\n"
            "        check({'d': ['b', 'c'], 'b': ['a'], 'c': ['a'], 'a': []})\n"
            "    def test_implicit_nodes(self):\n"
            "        check({'x': ['y']})\n"
            "    def test_cycle_attr(self):\n"
            "        try:\n"
            "            topo_sort({'a': ['b'], 'b': ['c'], 'c': ['a'], 'z': []})\n"
            "        except CycleError as e:\n"
            "            cyc = set(e.cycle)\n"
            "            self.assertGreaterEqual(len(cyc), 2)\n"
            "            self.assertTrue(cyc <= {'a', 'b', 'c'})\n"
            "        else:\n"
            "            self.fail('cycle not detected')\n",
            imports="from topo import topo_sort, CycleError\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 4. Exact-arithmetic ledger (float trap)
# --------------------------------------------------------------------------

_t(
    id="hard-decimal-ledger",
    category="hard-scratch",
    prompt=(
        "Write ledger.py with balances(path) -> dict mapping account name to its "
        "balance as decimal.Decimal (exact arithmetic — float rounding errors "
        "must not appear). Input file format, one transaction per line:\n"
        "  <account> <amount>\n"
        "where amount may contain thousands commas (1,234.56), an optional "
        "leading $ sign, and parentheses meaning negative: (45.00). Blank lines "
        "and lines starting with # are skipped. See transactions.txt for a "
        "sample; verify your implementation against it (cash should come to "
        "exactly 9.95)."
    ),
    files={
        "transactions.txt": (
            "# sample ledger\n"
            "cash 5.00\n"
            "cash $4.50\n"
            "cash 0.50\n"
            "cash (0.05)\n"
            "\n"
            "bank $1,234.56\n"
            "bank (234.56)\n"
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_sample(self):\n"
            "        b = balances('transactions.txt')\n"
            "        self.assertIsInstance(b['cash'], Decimal)\n"
            "        self.assertEqual(b['cash'], Decimal('9.95'))\n"
            "        self.assertEqual(b['bank'], Decimal('1000.00'))\n"
            "    def test_float_trap(self):\n"
            "        with open('_trap.txt', 'w') as f:\n"
            "            f.write('\\n'.join(['acct 0.10'] * 100))\n"
            "            f.write('\\nacct (0.05)\\n')\n"
            "        b = balances('_trap.txt')\n"
            "        self.assertIsInstance(b['acct'], Decimal)\n"
            "        self.assertEqual(b['acct'], Decimal('9.95'))\n",
            imports="from decimal import Decimal\nfrom ledger import balances\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 5. State machine from a README spec table
# --------------------------------------------------------------------------

_STATE_README = """# Order lifecycle

States: new, paid, shipped, delivered, cancelled, refunded
Actions: pay, ship, deliver, cancel, refund

| From state | Action  | To state  | Effect                      |
|------------|---------|-----------|-----------------------------|
| new        | pay     | paid      |                             |
| paid       | ship    | shipped   |                             |
| shipped    | deliver | delivered |                             |
| new        | cancel  | cancelled |                             |
| paid       | cancel  | cancelled | sets refund_due = True      |
| cancelled  | refund  | refunded  | only allowed if refund_due  |

Every other (state, action) combination is invalid and must raise
InvalidTransition with the exact message: `cannot <action> from <state>`
(a cancel from `new` leaves refund_due False; a disallowed refund raises
like any other invalid transition).

API (orders.py):
- new_order() -> order object with .state == 'new', .refund_due == False,
  .history == []
- transition(order, action) -> the same order, mutated; on success append
  (action, new_state) to order.history. Nothing is appended on failure.
- InvalidTransition exception class
"""

_t(
    id="hard-state-machine",
    category="hard-scratch",
    prompt=(
        "Implement orders.py exactly per the spec in README.md (states, "
        "transitions, effects, error message format, and history behavior). "
        "Write a quick test of your own and run it to verify."
    ),
    files={"README.md": _STATE_README},
    verify_files={
        "_verify.py": _unittest(
            "SETUP = {\n"
            "    'new': [],\n"
            "    'paid': ['pay'],\n"
            "    'shipped': ['pay', 'ship'],\n"
            "    'delivered': ['pay', 'ship', 'deliver'],\n"
            "    'cancelled_plain': ['cancel'],\n"
            "    'cancelled_refund': ['pay', 'cancel'],\n"
            "    'refunded': ['pay', 'cancel', 'refund'],\n"
            "}\n"
            "VALID = {\n"
            "    ('new', 'pay'): 'paid',\n"
            "    ('paid', 'ship'): 'shipped',\n"
            "    ('shipped', 'deliver'): 'delivered',\n"
            "    ('new', 'cancel'): 'cancelled',\n"
            "    ('paid', 'cancel'): 'cancelled',\n"
            "    ('cancelled_refund', 'refund'): 'refunded',\n"
            "}\n\n\n"
            "def build(label):\n"
            "    o = new_order()\n"
            "    for a in SETUP[label]:\n"
            "        transition(o, a)\n"
            "    return o\n\n\n"
            "class V(unittest.TestCase):\n"
            "    def test_full_matrix(self):\n"
            "        for label in SETUP:\n"
            "            for action in ['pay', 'ship', 'deliver', 'cancel', 'refund']:\n"
            "                o = build(label)\n"
            "                state = o.state\n"
            "                hist_before = list(o.history)\n"
            "                key = (label if label.startswith('cancelled') else state, action)\n"
            "                if key in VALID:\n"
            "                    transition(o, action)\n"
            "                    self.assertEqual(o.state, VALID[key], key)\n"
            "                    self.assertEqual(o.history, hist_before + [(action, VALID[key])])\n"
            "                else:\n"
            "                    with self.assertRaises(InvalidTransition, msg=key) as cm:\n"
            "                        transition(o, action)\n"
            "                    self.assertEqual(str(cm.exception), f'cannot {action} from {state}')\n"
            "                    self.assertEqual(o.history, hist_before)\n"
            "    def test_refund_due_flag(self):\n"
            "        self.assertFalse(build('cancelled_plain').refund_due)\n"
            "        self.assertTrue(build('cancelled_refund').refund_due)\n",
            imports="from orders import new_order, transition, InvalidTransition\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 6. Deep config merge with markers
# --------------------------------------------------------------------------

_t(
    id="hard-config-merge",
    category="hard-impl",
    prompt=(
        "Implement merge(base, override) in cfg.py for nested config dicts:\n"
        "- dicts merge recursively; scalars in override win;\n"
        "- a value of None in override deletes the key (deleting a missing key "
        "is fine);\n"
        "- lists replace the base list, EXCEPT when the override list's first "
        "element is the string '+append': then the remaining elements are "
        "appended to the base list (or to [] if the key is new).\n"
        "merge returns a new dict and must not mutate its inputs. Run the "
        "provided tests to verify."
    ),
    files={
        "cfg.py": "def merge(base, override):\n    raise NotImplementedError\n",
        "test_cfg.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_nested(self):\n"
            "        got = merge({'a': 1, 'b': {'x': 1, 'y': 2}}, {'b': {'y': 3}})\n"
            "        self.assertEqual(got, {'a': 1, 'b': {'x': 1, 'y': 3}})\n"
            "    def test_append(self):\n"
            "        self.assertEqual(merge({'l': [1, 2]}, {'l': ['+append', 3]}),\n"
            "                         {'l': [1, 2, 3]})\n",
            imports="from cfg import merge\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_replace_list(self):\n"
            "        self.assertEqual(merge({'l': [1, 2]}, {'l': [9]}), {'l': [9]})\n"
            "    def test_append_missing_base(self):\n"
            "        self.assertEqual(merge({}, {'l': ['+append', 1]}), {'l': [1]})\n"
            "    def test_delete(self):\n"
            "        self.assertEqual(merge({'a': 1, 'b': 2}, {'a': None, 'zz': None}),\n"
            "                         {'b': 2})\n"
            "    def test_no_mutation(self):\n"
            "        base = {'b': {'x': 1}, 'l': [1]}\n"
            "        merge(base, {'b': {'x': 2}, 'l': ['+append', 2]})\n"
            "        self.assertEqual(base, {'b': {'x': 1}, 'l': [1]})\n"
            "    def test_nested_delete_and_append(self):\n"
            "        got = merge({'s': {'l': [1], 'k': 5}}, {'s': {'l': ['+append', 2], 'k': None}})\n"
            "        self.assertEqual(got, {'s': {'l': [1, 2]}})\n",
            imports="from cfg import merge\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 7. Unified-diff applier (single hunk)
# --------------------------------------------------------------------------

_t(
    id="hard-diff-apply",
    category="hard-impl",
    prompt=(
        "Implement patcher.py with apply_patch(text, patch) -> new text, plus a "
        "PatchError exception. The patch is a single-hunk unified diff:\n"
        "- lines starting with --- or +++ are ignored;\n"
        "- one hunk header `@@ -<start>,<count> +<start>,<count> @@` where start "
        "is the 1-based first line of the hunk in the original text;\n"
        "- body lines start with ' ' (context), '-' (remove), '+' (add).\n"
        "Context and removed lines must match the original text exactly at the "
        "stated position, otherwise raise PatchError. text is newline-"
        "terminated; preserve that. Run the provided tests to verify."
    ),
    files={
        "patcher.py": (
            "class PatchError(Exception):\n    pass\n\n\n"
            "def apply_patch(text, patch):\n    raise NotImplementedError\n"
        ),
        "test_patcher.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_replace(self):\n"
            "        patch = '@@ -2,2 +2,2 @@\\n b\\n-c\\n+C\\n'\n"
            "        self.assertEqual(apply_patch('a\\nb\\nc\\nd\\n', patch), 'a\\nb\\nC\\nd\\n')\n"
            "    def test_mismatch(self):\n"
            "        patch = '@@ -1,1 +1,1 @@\\n-x\\n+y\\n'\n"
            "        with self.assertRaises(PatchError):\n"
            "            apply_patch('a\\n', patch)\n",
            imports="from patcher import apply_patch, PatchError\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_replace_middle(self):\n"
            "        patch = '@@ -2,2 +2,2 @@\\n b\\n-c\\n+C\\n'\n"
            "        self.assertEqual(apply_patch('a\\nb\\nc\\nd\\n', patch), 'a\\nb\\nC\\nd\\n')\n"
            "    def test_headers_ignored(self):\n"
            "        patch = '--- a/f\\n+++ b/f\\n@@ -1,1 +1,1 @@\\n-a\\n+b\\n'\n"
            "        self.assertEqual(apply_patch('a\\n', patch), 'b\\n')\n"
            "    def test_append_at_end(self):\n"
            "        patch = '@@ -1,1 +1,2 @@\\n a\\n+b\\n'\n"
            "        self.assertEqual(apply_patch('a\\n', patch), 'a\\nb\\n')\n"
            "    def test_pure_insert_before(self):\n"
            "        patch = '@@ -1,1 +1,2 @@\\n+z\\n a\\n'\n"
            "        self.assertEqual(apply_patch('a\\nb\\n', patch), 'z\\na\\nb\\n')\n"
            "    def test_context_mismatch_raises(self):\n"
            "        patch = '@@ -2,1 +2,1 @@\\n-x\\n+y\\n'\n"
            "        with self.assertRaises(PatchError):\n"
            "            apply_patch('a\\nb\\n', patch)\n",
            imports="from patcher import apply_patch, PatchError\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 8. Performance gate: anagram grouping at scale
# --------------------------------------------------------------------------

_t(
    id="hard-perf-anagrams",
    category="hard-perf",
    prompt=(
        "Implement anagram_groups(words) in anagrams.py: treat words as a set "
        "(ignore duplicates) and return the groups of 2 or more distinct words "
        "that are anagrams of each other, as a list of lists (order of groups "
        "and within groups doesn't matter). It must handle tens of thousands of "
        "words in well under 15 seconds — an all-pairs comparison is too slow. "
        "Run the provided tests to verify correctness."
    ),
    files={
        "anagrams.py": "def anagram_groups(words):\n    raise NotImplementedError\n",
        "test_anagrams.py": _unittest(
            "def norm(groups):\n"
            "    return {frozenset(g) for g in groups}\n\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_small(self):\n"
            "        got = norm(anagram_groups(['eat', 'tea', 'tan', 'nat', 'bat']))\n"
            "        self.assertEqual(got, {frozenset({'eat', 'tea'}), frozenset({'tan', 'nat'})})\n"
            "    def test_dupes_ignored(self):\n"
            "        self.assertEqual(norm(anagram_groups(['ab', 'ab', 'ba'])),\n"
            "                         {frozenset({'ab', 'ba'})})\n",
            imports="from anagrams import anagram_groups\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_scale_and_correctness(self):\n"
            "        rng = random.Random(42)\n"
            "        letters = 'abcdefghij'\n"
            "        words = []\n"
            "        for _ in range(4000):\n"
            "            w = ''.join(rng.choice(letters) for _ in range(8))\n"
            "            words.append(w)\n"
            "            for _ in range(4):\n"
            "                l = list(w)\n"
            "                rng.shuffle(l)\n"
            "                words.append(''.join(l))\n"
            "        rng.shuffle(words)\n"
            "        t0 = time.monotonic()\n"
            "        got = anagram_groups(words)\n"
            "        dt = time.monotonic() - t0\n"
            "        self.assertLess(dt, 15, f'too slow: {dt:.1f}s')\n"
            "        ref = collections.defaultdict(set)\n"
            "        for w in set(words):\n"
            "            ref[''.join(sorted(w))].add(w)\n"
            "        expected = {frozenset(g) for g in ref.values() if len(g) > 1}\n"
            "        self.assertEqual({frozenset(g) for g in got}, expected)\n",
            imports="import collections\nimport random\nimport time\nfrom anagrams import anagram_groups\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 9. Multi-file parameter threading
# --------------------------------------------------------------------------

_t(
    id="hard-thread-discount",
    category="hard-multi",
    prompt=(
        "This mini store package computes totals through three layers. Add "
        "discount support: every function gains an optional discount keyword "
        "argument (a fraction, default 0.0) threaded through all layers — "
        "line_total applies it per line before rounding. Existing behavior "
        "without discount must be unchanged. The provided tests must pass; run "
        "them to verify."
    ),
    files={
        "store/__init__.py": "",
        "store/pricing.py": (
            "def line_total(qty, unit_price):\n"
            "    return round(qty * unit_price, 2)\n"
        ),
        "store/cart.py": (
            "from .pricing import line_total\n\n\n"
            "def cart_total(items):\n"
            '    """items: list of (qty, unit_price) tuples."""\n'
            "    return round(sum(line_total(q, p) for q, p in items), 2)\n"
        ),
        "store/report.py": (
            "from .cart import cart_total\n\n\n"
            "def receipt(items):\n"
            "    return f'TOTAL: {cart_total(items):.2f}'\n"
        ),
        "test_store.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_no_discount_unchanged(self):\n"
            "        self.assertEqual(line_total(2, 10.0), 20.0)\n"
            "        self.assertEqual(cart_total([(1, 10.0), (2, 10.0)]), 30.0)\n"
            "    def test_discount_threads_through(self):\n"
            "        self.assertEqual(line_total(2, 10.0, discount=0.1), 18.0)\n"
            "        self.assertEqual(cart_total([(1, 10.0), (2, 10.0)], discount=0.1), 27.0)\n"
            "        self.assertEqual(receipt([(1, 10.0), (2, 10.0)], discount=0.1), 'TOTAL: 27.00')\n",
            imports="from store.pricing import line_total\nfrom store.cart import cart_total\nfrom store.report import receipt\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_defaults_unchanged(self):\n"
            "        self.assertEqual(cart_total([(3, 3.33)]), 9.99)\n"
            "        self.assertEqual(receipt([(1, 5.0)]), 'TOTAL: 5.00')\n"
            "    def test_threading(self):\n"
            "        self.assertEqual(line_total(2, 10.0, discount=0.25), 15.0)\n"
            "        self.assertEqual(cart_total([(2, 10.0), (1, 4.0)], discount=0.5), 12.0)\n"
            "        self.assertEqual(receipt([(2, 10.0)], discount=0.05), 'TOTAL: 19.00')\n",
            imports="from store.pricing import line_total\nfrom store.cart import cart_total\nfrom store.report import receipt\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 10. Bug far from symptom: shared cache ignores its key
# --------------------------------------------------------------------------

_t(
    id="hard-bug-shared-cache",
    category="hard-debug",
    prompt=(
        "The test in this repo fails, but only on the second call — the first "
        "assertion passes. Find the root cause, fix it with a minimal change "
        "(the caching itself should stay), and verify the tests pass."
    ),
    files={
        "settings.py": (
            "_cache = {}\n\n\n"
            "def load_settings(env):\n"
            '    """Return the settings dict for env. Cached for speed."""\n'
            "    if 'settings' not in _cache:\n"
            "        _cache['settings'] = _build(env)\n"
            "    return _cache['settings']\n\n\n"
            "def _build(env):\n"
            "    return {'name': env, 'debug': env == 'dev'}\n"
        ),
        "test_settings.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_envs_are_distinct(self):\n"
            "        self.assertEqual(load_settings('dev')['name'], 'dev')\n"
            "        self.assertEqual(load_settings('prod')['name'], 'prod')\n"
            "        self.assertFalse(load_settings('prod')['debug'])\n",
            imports="from settings import load_settings\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_distinct(self):\n"
            "        self.assertEqual(load_settings('dev')['name'], 'dev')\n"
            "        self.assertEqual(load_settings('prod')['name'], 'prod')\n"
            "        self.assertEqual(load_settings('dev')['name'], 'dev')\n"
            "    def test_still_cached(self):\n"
            "        a = load_settings('dev')\n"
            "        b = load_settings('dev')\n"
            "        self.assertIs(a, b)\n",
            imports="from settings import load_settings\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 11. Bug far from symptom: aliasing mutation across modules
# --------------------------------------------------------------------------

_t(
    id="hard-bug-aliasing",
    category="hard-debug",
    prompt=(
        "The test in this repo fails in a confusing way: the winners are right "
        "but first_submitted is wrong. Find the root cause, fix it with a "
        "minimal change, and verify the tests pass."
    ),
    files={
        "ranking.py": (
            "def top_n(scores, n):\n"
            '    """Return the n highest scores, best first."""\n'
            "    scores.sort(reverse=True)\n"
            "    return scores[:n]\n"
        ),
        "contest.py": (
            "from ranking import top_n\n\n\n"
            "def summarize(scores):\n"
            '    """scores arrive in submission order."""\n'
            "    winners = top_n(scores, 3)\n"
            "    return {'winners': winners, 'first_submitted': scores[0]}\n"
        ),
        "test_contest.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_summary(self):\n"
            "        got = summarize([5, 9, 1, 7])\n"
            "        self.assertEqual(got['winners'], [9, 7, 5])\n"
            "        self.assertEqual(got['first_submitted'], 5)\n",
            imports="from contest import summarize\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_summary(self):\n"
            "        got = summarize([5, 9, 1, 7])\n"
            "        self.assertEqual(got['winners'], [9, 7, 5])\n"
            "        self.assertEqual(got['first_submitted'], 5)\n"
            "    def test_caller_list_not_mutated(self):\n"
            "        data = [3, 1, 2]\n"
            "        top_n(data, 2)\n"
            "        self.assertEqual(data, [3, 1, 2])\n",
            imports="from contest import summarize\nfrom ranking import top_n\n",
        ),
    },
)

# --------------------------------------------------------------------------
# 12. Cross-module dedup refactor with structural check
# --------------------------------------------------------------------------

_t(
    id="hard-refactor-extract",
    category="hard-multi",
    prompt=(
        "Three modules (envparse.py, tagparse.py, metaparse.py) each contain a "
        "copy of the same 'key=value;key=value' splitting logic, differing only "
        "in post-processing. Extract the shared splitting into a function "
        "split_pairs(text) in a new module common.py — returning the list of "
        "(key, value) tuples, both stripped — and make all three modules use it "
        "(no leftover duplicated splitting). Each module's observable behavior "
        "must not change. Run the tests to verify."
    ),
    files={
        "envparse.py": (
            "def parse_env(text):\n"
            '    """UPPERCASE keys."""\n'
            "    pairs = []\n"
            "    for part in text.split(';'):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        key, _, value = part.partition('=')\n"
            "        pairs.append((key.strip(), value.strip()))\n"
            "    return {k.upper(): v for k, v in pairs}\n"
        ),
        "tagparse.py": (
            "def parse_tags(text):\n"
            '    """lowercase values."""\n'
            "    pairs = []\n"
            "    for part in text.split(';'):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        key, _, value = part.partition('=')\n"
            "        pairs.append((key.strip(), value.strip()))\n"
            "    return {k: v.lower() for k, v in pairs}\n"
        ),
        "metaparse.py": (
            "def parse_meta(text):\n"
            '    """Keys and values kept as-is; empty values dropped."""\n'
            "    pairs = []\n"
            "    for part in text.split(';'):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        key, _, value = part.partition('=')\n"
            "        pairs.append((key.strip(), value.strip()))\n"
            "    return {k: v for k, v in pairs if v}\n"
        ),
        "test_parsers.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_env(self):\n"
            "        self.assertEqual(parse_env('a=1; b=2'), {'A': '1', 'B': '2'})\n"
            "    def test_tags(self):\n"
            "        self.assertEqual(parse_tags('x=Foo;y=BAR'), {'x': 'foo', 'y': 'bar'})\n"
            "    def test_meta(self):\n"
            "        self.assertEqual(parse_meta('a=1;b=;c=3'), {'a': '1', 'c': '3'})\n",
            imports="from envparse import parse_env\nfrom tagparse import parse_tags\nfrom metaparse import parse_meta\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_behavior_pinned(self):\n"
            "        self.assertEqual(parse_env('a=1; b = 2 ;'), {'A': '1', 'B': '2'})\n"
            "        self.assertEqual(parse_tags(' x=Foo; y=BAR'), {'x': 'foo', 'y': 'bar'})\n"
            "        self.assertEqual(parse_meta('a=1;b=;c=3'), {'a': '1', 'c': '3'})\n"
            "        self.assertEqual(parse_env(''), {})\n"
            "    def test_shared_helper_exists(self):\n"
            "        import common\n"
            "        self.assertTrue(callable(common.split_pairs))\n"
            "        self.assertEqual(common.split_pairs('a=1; b=2'), [('a', '1'), ('b', '2')])\n"
            "    def test_all_modules_use_it(self):\n"
            "        for mod in ('envparse', 'tagparse', 'metaparse'):\n"
            "            src = open(mod + '.py').read()\n"
            "            self.assertIn('split_pairs', src, mod)\n"
            "            self.assertNotIn(\"partition('=')\", src, mod)\n",
            imports="from envparse import parse_env\nfrom tagparse import parse_tags\nfrom metaparse import parse_meta\n",
        ),
    },
)


assert len(HARD_TASKS) == 12, f"expected 12 hard tasks, have {len(HARD_TASKS)}"
assert len({t.id for t in HARD_TASKS}) == 12, "duplicate task ids"
