"""30 self-contained SWE benchmark tasks.

Each task gives the agent a small workspace (``files``) and a ``prompt``.
After the agent finishes, the runner writes ``verify_files`` into the
workspace — overwriting any tampering with visible tests — and runs
``check`` (exit 0 = pass). The agent never sees the verification files.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Task:
    id: str
    category: str
    prompt: str
    files: dict[str, str]
    verify_files: dict[str, str]
    check: str = "python3 _verify.py"


def _unittest(body: str, imports: str = "") -> str:
    return (
        "import unittest\n" + imports + "\n\n" + body +
        '\n\nif __name__ == "__main__":\n    unittest.main(verbosity=0)\n'
    )


FIX_PROMPT = (
    "The tests in this repo fail. Run them, find the bug, fix it with a "
    "minimal change to the implementation (not the tests), and verify the "
    "tests pass."
)
IMPL_PROMPT = (
    "Implement the stubbed function so the provided tests pass. Run the "
    "tests to verify."
)

TASKS: list[Task] = []


def _t(**kw) -> None:
    TASKS.append(Task(**kw))


# --------------------------------------------------------------------------
# A. Bug fixes — failing tests provided, implementation has a planted bug
# --------------------------------------------------------------------------

_t(
    id="fix-median-sort",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "stats.py": (
            "def median(values):\n"
            '    """Return the median of a non-empty list of numbers."""\n'
            "    n = len(values)\n"
            "    mid = n // 2\n"
            "    if n % 2:\n"
            "        return values[mid]\n"
            "    return (values[mid - 1] + values[mid]) / 2\n"
        ),
        "test_stats.py": _unittest(
            "class TestMedian(unittest.TestCase):\n"
            "    def test_odd_unsorted(self):\n"
            "        self.assertEqual(median([9, 1, 5]), 5)\n"
            "    def test_even_unsorted(self):\n"
            "        self.assertEqual(median([7, 1, 3, 5]), 4.0)\n",
            imports="from stats import median\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_odd(self):\n"
            "        self.assertEqual(median([9, 1, 5]), 5)\n"
            "    def test_even(self):\n"
            "        self.assertEqual(median([7, 1, 3, 5]), 4.0)\n"
            "    def test_extra(self):\n"
            "        self.assertEqual(median([3, 2, 1, 5, 4]), 3)\n",
            imports="from stats import median\n",
        ),
    },
)

_t(
    id="fix-sum-range",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "numbersum.py": (
            "def sum_to(n):\n"
            '    """Sum the integers 1..n inclusive."""\n'
            "    total = 0\n"
            "    for i in range(1, n):\n"
            "        total += i\n"
            "    return total\n"
        ),
        "test_numbersum.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_five(self):\n"
            "        self.assertEqual(sum_to(5), 15)\n"
            "    def test_one(self):\n"
            "        self.assertEqual(sum_to(1), 1)\n",
            imports="from numbersum import sum_to\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_five(self):\n"
            "        self.assertEqual(sum_to(5), 15)\n"
            "    def test_hundred(self):\n"
            "        self.assertEqual(sum_to(100), 5050)\n",
            imports="from numbersum import sum_to\n",
        ),
    },
)

_t(
    id="fix-binary-search",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "search.py": (
            "def binary_search(arr, target):\n"
            '    """Return the index of target in sorted arr, or -1."""\n'
            "    lo, hi = 0, len(arr) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        if target > arr[mid]:\n"
            "            hi = mid - 1\n"
            "        else:\n"
            "            lo = mid + 1\n"
            "    return -1\n"
        ),
        "test_search.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_found(self):\n"
            "        self.assertEqual(binary_search([1, 3, 5, 7, 9], 7), 3)\n"
            "    def test_missing(self):\n"
            "        self.assertEqual(binary_search([1, 3, 5], 4), -1)\n",
            imports="from search import binary_search\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_found(self):\n"
            "        self.assertEqual(binary_search([1, 3, 5, 7, 9], 7), 3)\n"
            "    def test_first(self):\n"
            "        self.assertEqual(binary_search([2, 4, 6, 8], 2), 0)\n"
            "    def test_last(self):\n"
            "        self.assertEqual(binary_search([2, 4, 6, 8], 8), 3)\n"
            "    def test_missing(self):\n"
            "        self.assertEqual(binary_search([1, 3, 5], 4), -1)\n",
            imports="from search import binary_search\n",
        ),
    },
)

_t(
    id="fix-mutable-default",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "collect.py": (
            "def append_item(item, bucket=[]):\n"
            '    """Append item to bucket (a new list unless one is given)."""\n'
            "    bucket.append(item)\n"
            "    return bucket\n"
        ),
        "test_collect.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_fresh_bucket_each_call(self):\n"
            "        self.assertEqual(append_item(1), [1])\n"
            "        self.assertEqual(append_item(2), [2])\n"
            "    def test_explicit_bucket(self):\n"
            "        b = [0]\n"
            "        self.assertEqual(append_item(1, b), [0, 1])\n",
            imports="from collect import append_item\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_fresh(self):\n"
            "        append_item('x')\n"
            "        self.assertEqual(append_item(2), [2])\n"
            "    def test_explicit(self):\n"
            "        self.assertEqual(append_item(1, [0]), [0, 1])\n",
            imports="from collect import append_item\n",
        ),
    },
)

_t(
    id="fix-title-case",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "textutil.py": (
            "def title_case(sentence):\n"
            '    """Capitalize each word; the rest of each word lowercase."""\n'
            "    return ' '.join(w.upper() for w in sentence.split())\n"
        ),
        "test_textutil.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(title_case('hello world'), 'Hello World')\n"
            "    def test_mixed(self):\n"
            "        self.assertEqual(title_case('hELLO wORLD'), 'Hello World')\n",
            imports="from textutil import title_case\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(title_case('hello world'), 'Hello World')\n"
            "    def test_single(self):\n"
            "        self.assertEqual(title_case('pYTHON'), 'Python')\n",
            imports="from textutil import title_case\n",
        ),
    },
)

_t(
    id="fix-missing-key",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "userprofile.py": (
            "def display_name(user):\n"
            '    """Prefer nickname, fall back to name, then \'anonymous\'."""\n'
            "    if user['nickname']:\n"
            "        return user['nickname']\n"
            "    if user['name']:\n"
            "        return user['name']\n"
            "    return 'anonymous'\n"
        ),
        "test_userprofile.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_nickname(self):\n"
            "        self.assertEqual(display_name({'nickname': 'kit', 'name': 'K'}), 'kit')\n"
            "    def test_missing_keys(self):\n"
            "        self.assertEqual(display_name({}), 'anonymous')\n"
            "    def test_name_only(self):\n"
            "        self.assertEqual(display_name({'name': 'Kim'}), 'Kim')\n",
            imports="from userprofile import display_name\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_missing(self):\n"
            "        self.assertEqual(display_name({}), 'anonymous')\n"
            "    def test_name_only(self):\n"
            "        self.assertEqual(display_name({'name': 'Kim'}), 'Kim')\n"
            "    def test_nickname(self):\n"
            "        self.assertEqual(display_name({'nickname': 'kit'}), 'kit')\n",
            imports="from userprofile import display_name\n",
        ),
    },
)

_t(
    id="fix-fib-base",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "fib.py": (
            "def fib(n):\n"
            '    """Return the n-th Fibonacci number; fib(1) == fib(2) == 1."""\n'
            "    if n <= 2:\n"
            "        return n\n"
            "    return fib(n - 1) + fib(n - 2)\n"
        ),
        "test_fib.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_small(self):\n"
            "        self.assertEqual([fib(i) for i in range(1, 7)], [1, 1, 2, 3, 5, 8])\n",
            imports="from fib import fib\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_small(self):\n"
            "        self.assertEqual([fib(i) for i in range(1, 7)], [1, 1, 2, 3, 5, 8])\n"
            "    def test_ten(self):\n"
            "        self.assertEqual(fib(10), 55)\n",
            imports="from fib import fib\n",
        ),
    },
)

_t(
    id="fix-int-division",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "grades.py": (
            "def average(scores):\n"
            '    """Return the arithmetic mean of scores as a float."""\n'
            "    return sum(scores) // len(scores)\n"
        ),
        "test_grades.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_mean(self):\n"
            "        self.assertEqual(average([1, 2]), 1.5)\n"
            "    def test_whole(self):\n"
            "        self.assertEqual(average([2, 4]), 3.0)\n",
            imports="from grades import average\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_mean(self):\n"
            "        self.assertEqual(average([1, 2]), 1.5)\n"
            "    def test_third(self):\n"
            "        self.assertAlmostEqual(average([1, 1, 2]), 4 / 3)\n",
            imports="from grades import average\n",
        ),
    },
)

_t(
    id="fix-inverted-filter",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "emails.py": (
            "def valid_emails(addresses):\n"
            '    """Keep only addresses containing exactly one \'@\'."""\n'
            "    return [a for a in addresses if a.count('@') != 1]\n"
        ),
        "test_emails.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_filter(self):\n"
            "        got = valid_emails(['a@b.com', 'bad', 'x@@y'])\n"
            "        self.assertEqual(got, ['a@b.com'])\n",
            imports="from emails import valid_emails\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_filter(self):\n"
            "        self.assertEqual(valid_emails(['a@b.com', 'bad', 'x@@y']), ['a@b.com'])\n"
            "    def test_empty(self):\n"
            "        self.assertEqual(valid_emails(['nope']), [])\n",
            imports="from emails import valid_emails\n",
        ),
    },
)

_t(
    id="fix-chunk-slice",
    category="bugfix",
    prompt=FIX_PROMPT,
    files={
        "chunks.py": (
            "def chunk(items, size):\n"
            '    """Split items into consecutive lists of at most `size`."""\n'
            "    out = []\n"
            "    for i in range(0, len(items), size):\n"
            "        out.append(items[i:i + size - 1])\n"
            "    return out\n"
        ),
        "test_chunks.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_even(self):\n"
            "        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])\n"
            "    def test_ragged(self):\n"
            "        self.assertEqual(chunk([1, 2, 3], 2), [[1, 2], [3]])\n",
            imports="from chunks import chunk\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_even(self):\n"
            "        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])\n"
            "    def test_ragged(self):\n"
            "        self.assertEqual(chunk([1, 2, 3], 2), [[1, 2], [3]])\n"
            "    def test_one(self):\n"
            "        self.assertEqual(chunk([1, 2], 1), [[1], [2]])\n",
            imports="from chunks import chunk\n",
        ),
    },
)

# --------------------------------------------------------------------------
# B. Implement from failing tests — stub raises NotImplementedError
# --------------------------------------------------------------------------


def _stub(name: str, doc: str, args: str = "value") -> str:
    return (
        f"def {name}({args}):\n"
        f'    """{doc}"""\n'
        f"    raise NotImplementedError\n"
    )


_t(
    id="impl-rle-encode",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "rle.py": _stub("rle_encode", "Run-length encode: 'aaabb' -> [('a', 3), ('b', 2)].", "text"),
        "test_rle.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(rle_encode('aaabb'), [('a', 3), ('b', 2)])\n"
            "    def test_empty(self):\n"
            "        self.assertEqual(rle_encode(''), [])\n"
            "    def test_single(self):\n"
            "        self.assertEqual(rle_encode('x'), [('x', 1)])\n",
            imports="from rle import rle_encode\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(rle_encode('aaabb'), [('a', 3), ('b', 2)])\n"
            "    def test_alternating(self):\n"
            "        self.assertEqual(rle_encode('aba'), [('a', 1), ('b', 1), ('a', 1)])\n"
            "    def test_empty(self):\n"
            "        self.assertEqual(rle_encode(''), [])\n",
            imports="from rle import rle_encode\n",
        ),
    },
)

_t(
    id="impl-balanced-parens",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "parens.py": _stub(
            "is_balanced", "True if every (, [, { closes in the right order.", "text"
        ),
        "test_parens.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(is_balanced('([]{})'))\n"
            "    def test_bad_order(self):\n"
            "        self.assertFalse(is_balanced('([)]'))\n"
            "    def test_unclosed(self):\n"
            "        self.assertFalse(is_balanced('(('))\n",
            imports="from parens import is_balanced\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(is_balanced('([]{})'))\n"
            "    def test_bad(self):\n"
            "        self.assertFalse(is_balanced('([)]'))\n"
            "    def test_close_first(self):\n"
            "        self.assertFalse(is_balanced(')('))\n"
            "    def test_empty(self):\n"
            "        self.assertTrue(is_balanced(''))\n",
            imports="from parens import is_balanced\n",
        ),
    },
)

_t(
    id="impl-roman-to-int",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "roman.py": _stub("roman_to_int", "Convert a Roman numeral like 'XIV' to 14.", "s"),
        "test_roman.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_simple(self):\n"
            "        self.assertEqual(roman_to_int('VII'), 7)\n"
            "    def test_subtractive(self):\n"
            "        self.assertEqual(roman_to_int('XIV'), 14)\n"
            "    def test_big(self):\n"
            "        self.assertEqual(roman_to_int('MCMXCIV'), 1994)\n",
            imports="from roman import roman_to_int\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_subtractive(self):\n"
            "        self.assertEqual(roman_to_int('XIV'), 14)\n"
            "    def test_nine(self):\n"
            "        self.assertEqual(roman_to_int('IX'), 9)\n"
            "    def test_big(self):\n"
            "        self.assertEqual(roman_to_int('MCMXCIV'), 1994)\n",
            imports="from roman import roman_to_int\n",
        ),
    },
)

_t(
    id="impl-flatten",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "flat.py": _stub(
            "flatten", "Flatten arbitrarily nested lists: [1, [2, [3]]] -> [1, 2, 3].", "nested"
        ),
        "test_flat.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_nested(self):\n"
            "        self.assertEqual(flatten([1, [2, [3, 4]], 5]), [1, 2, 3, 4, 5])\n"
            "    def test_flat(self):\n"
            "        self.assertEqual(flatten([1, 2]), [1, 2])\n",
            imports="from flat import flatten\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_nested(self):\n"
            "        self.assertEqual(flatten([1, [2, [3, 4]], 5]), [1, 2, 3, 4, 5])\n"
            "    def test_deep(self):\n"
            "        self.assertEqual(flatten([[[[7]]]]), [7])\n"
            "    def test_empty(self):\n"
            "        self.assertEqual(flatten([]), [])\n",
            imports="from flat import flatten\n",
        ),
    },
)

_t(
    id="impl-caesar",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "caesar.py": (
            "def encode(text, shift):\n"
            '    """Caesar-shift letters by `shift`; keep case; pass through non-letters."""\n'
            "    raise NotImplementedError\n"
        ),
        "test_caesar.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(encode('abc', 2), 'cde')\n"
            "    def test_wrap(self):\n"
            "        self.assertEqual(encode('xyz', 3), 'abc')\n"
            "    def test_case_and_punct(self):\n"
            "        self.assertEqual(encode('Hi, Zoe!', 1), 'Ij, Apf!')\n",
            imports="from caesar import encode\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_wrap(self):\n"
            "        self.assertEqual(encode('xyz', 3), 'abc')\n"
            "    def test_case(self):\n"
            "        self.assertEqual(encode('Hi, Zoe!', 1), 'Ij, Apf!')\n"
            "    def test_zero(self):\n"
            "        self.assertEqual(encode('same', 0), 'same')\n",
            imports="from caesar import encode\n",
        ),
    },
)

_t(
    id="impl-word-freq",
    category="implement",
    prompt=IMPL_PROMPT,
    files={
        "freq.py": _stub(
            "word_frequencies",
            "Case-insensitive word counts, ignoring punctuation: "
            "'The cat, the DOG.' -> {'the': 2, 'cat': 1, 'dog': 1}.",
            "text",
        ),
        "test_freq.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_counts(self):\n"
            "        self.assertEqual(word_frequencies('The cat, the DOG.'),\n"
            "                         {'the': 2, 'cat': 1, 'dog': 1})\n"
            "    def test_empty(self):\n"
            "        self.assertEqual(word_frequencies(''), {})\n",
            imports="from freq import word_frequencies\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_counts(self):\n"
            "        self.assertEqual(word_frequencies('The cat, the DOG.'),\n"
            "                         {'the': 2, 'cat': 1, 'dog': 1})\n"
            "    def test_apostrophe_free(self):\n"
            "        self.assertEqual(word_frequencies('go go GO!'), {'go': 3})\n",
            imports="from freq import word_frequencies\n",
        ),
    },
)

# --------------------------------------------------------------------------
# C. Feature additions to existing working code
# --------------------------------------------------------------------------

_t(
    id="feat-dedupe-keep-last",
    category="feature",
    prompt=(
        "dedupe() currently keeps the first occurrence of each item. Add a "
        "keep parameter ('first' by default, or 'last') so callers can keep "
        "the last occurrence instead, preserving the order in which the kept "
        "occurrences appear. The provided tests must pass; run them to verify."
    ),
    files={
        "dedupe.py": (
            "def dedupe(items):\n"
            '    """Remove duplicates, keeping the first occurrence of each item."""\n'
            "    seen = set()\n"
            "    out = []\n"
            "    for x in items:\n"
            "        if x not in seen:\n"
            "            seen.add(x)\n"
            "            out.append(x)\n"
            "    return out\n"
        ),
        "test_dedupe.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_first(self):\n"
            "        self.assertEqual(dedupe([1, 2, 1, 3]), [1, 2, 3])\n"
            "    def test_last(self):\n"
            "        self.assertEqual(dedupe([1, 2, 1, 3], keep='last'), [2, 1, 3])\n",
            imports="from dedupe import dedupe\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_first_default(self):\n"
            "        self.assertEqual(dedupe([1, 2, 1, 3]), [1, 2, 3])\n"
            "    def test_last(self):\n"
            "        self.assertEqual(dedupe([1, 2, 1, 3], keep='last'), [2, 1, 3])\n"
            "    def test_last_strings(self):\n"
            "        self.assertEqual(dedupe(list('abcab'), keep='last'), ['c', 'a', 'b'])\n",
            imports="from dedupe import dedupe\n",
        ),
    },
)

_t(
    id="feat-validate-negative",
    category="feature",
    prompt=(
        "sqrt_int() should raise ValueError (with any message) when given a "
        "negative number, instead of returning nonsense. Make the provided "
        "tests pass; run them to verify."
    ),
    files={
        "mathx.py": (
            "def sqrt_int(n):\n"
            '    """Integer square root via search."""\n'
            "    x = 0\n"
            "    while (x + 1) * (x + 1) <= n:\n"
            "        x += 1\n"
            "    return x\n"
        ),
        "test_mathx.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_value(self):\n"
            "        self.assertEqual(sqrt_int(16), 4)\n"
            "    def test_negative_raises(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            sqrt_int(-1)\n",
            imports="from mathx import sqrt_int\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_value(self):\n"
            "        self.assertEqual(sqrt_int(17), 4)\n"
            "    def test_negative(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            sqrt_int(-5)\n",
            imports="from mathx import sqrt_int\n",
        ),
    },
)

_t(
    id="feat-stack-peek",
    category="feature",
    prompt=(
        "Extend the Stack class with peek() (return the top item without "
        "removing it; raise IndexError when empty) and is_empty(). The "
        "provided tests must pass; run them to verify."
    ),
    files={
        "stack.py": (
            "class Stack:\n"
            "    def __init__(self):\n"
            "        self._items = []\n\n"
            "    def push(self, item):\n"
            "        self._items.append(item)\n\n"
            "    def pop(self):\n"
            "        return self._items.pop()\n"
        ),
        "test_stack.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_peek(self):\n"
            "        s = Stack(); s.push(1); s.push(2)\n"
            "        self.assertEqual(s.peek(), 2)\n"
            "        self.assertEqual(s.pop(), 2)\n"
            "    def test_empty(self):\n"
            "        s = Stack()\n"
            "        self.assertTrue(s.is_empty())\n"
            "        s.push(1)\n"
            "        self.assertFalse(s.is_empty())\n",
            imports="from stack import Stack\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_peek_keeps(self):\n"
            "        s = Stack(); s.push(5)\n"
            "        self.assertEqual(s.peek(), 5)\n"
            "        self.assertFalse(s.is_empty())\n"
            "    def test_peek_empty_raises(self):\n"
            "        with self.assertRaises(IndexError):\n"
            "            Stack().peek()\n",
            imports="from stack import Stack\n",
        ),
    },
)

_t(
    id="feat-parse-dates",
    category="feature",
    prompt=(
        "load_records() returns the joined date as a string. Change it to "
        "return a datetime.date for the second field. The provided tests "
        "must pass; run them to verify."
    ),
    files={
        "records.py": (
            "def load_records(lines):\n"
            '    """Parse \'name,YYYY-MM-DD\' lines into dicts."""\n'
            "    out = []\n"
            "    for line in lines:\n"
            "        name, joined = line.strip().split(',')\n"
            "        out.append({'name': name, 'joined': joined})\n"
            "    return out\n"
        ),
        "test_records.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_date_type(self):\n"
            "        recs = load_records(['ada,2024-01-05'])\n"
            "        self.assertEqual(recs[0]['joined'], datetime.date(2024, 1, 5))\n",
            imports="import datetime\nfrom records import load_records\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_date(self):\n"
            "        recs = load_records(['ada,2024-01-05', 'bo,2023-12-31'])\n"
            "        self.assertEqual(recs[1]['joined'], datetime.date(2023, 12, 31))\n"
            "        self.assertEqual(recs[0]['name'], 'ada')\n",
            imports="import datetime\nfrom records import load_records\n",
        ),
    },
)

_t(
    id="feat-max-key",
    category="feature",
    prompt=(
        "Add an optional key= keyword argument to my_max (like the builtin "
        "max) that selects the comparison value for each item. The provided "
        "tests must pass; run them to verify."
    ),
    files={
        "mymax.py": (
            "def my_max(items):\n"
            '    """Return the largest item of a non-empty sequence."""\n'
            "    best = items[0]\n"
            "    for x in items[1:]:\n"
            "        if x > best:\n"
            "            best = x\n"
            "    return best\n"
        ),
        "test_mymax.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_plain(self):\n"
            "        self.assertEqual(my_max([3, 1, 2]), 3)\n"
            "    def test_key(self):\n"
            "        self.assertEqual(my_max(['bb', 'a', 'ccc'], key=len), 'ccc')\n",
            imports="from mymax import my_max\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_plain(self):\n"
            "        self.assertEqual(my_max([3, 1, 2]), 3)\n"
            "    def test_key(self):\n"
            "        self.assertEqual(my_max([-5, 3], key=abs), -5)\n",
            imports="from mymax import my_max\n",
        ),
    },
)

_t(
    id="feat-sort-reverse-flag",
    category="feature",
    prompt=(
        "sortlines.py sorts stdin-provided lines via sort_lines(). Add "
        "reverse-order support: sort_lines(lines, reverse=False) and a "
        "--reverse CLI flag that enables it. The provided tests must pass; "
        "run them to verify."
    ),
    files={
        "sortlines.py": (
            "import argparse\n"
            "import sys\n\n\n"
            "def sort_lines(lines):\n"
            '    """Return lines sorted ascending."""\n'
            "    return sorted(lines)\n\n\n"
            "def main():\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.parse_args()\n"
            "    for line in sort_lines([l.rstrip('\\n') for l in sys.stdin]):\n"
            "        print(line)\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "test_sortlines.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_plain(self):\n"
            "        self.assertEqual(sort_lines(['b', 'a']), ['a', 'b'])\n"
            "    def test_reverse(self):\n"
            "        self.assertEqual(sort_lines(['b', 'a', 'c'], reverse=True), ['c', 'b', 'a'])\n",
            imports="from sortlines import sort_lines\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_reverse_fn(self):\n"
            "        self.assertEqual(sort_lines(['b', 'a', 'c'], reverse=True), ['c', 'b', 'a'])\n"
            "    def test_cli_flag(self):\n"
            "        out = subprocess.run(\n"
            "            [sys.executable, 'sortlines.py', '--reverse'],\n"
            "            input='a\\nc\\nb\\n', capture_output=True, text=True)\n"
            "        self.assertEqual(out.stdout.split(), ['c', 'b', 'a'])\n",
            imports="import subprocess\nimport sys\nfrom sortlines import sort_lines\n",
        ),
    },
)

# --------------------------------------------------------------------------
# D. Refactors / precise edits — verified against source text AND behavior
# --------------------------------------------------------------------------

_t(
    id="ref-rename-function",
    category="refactor",
    prompt=(
        "Rename the function calc to calculate_total everywhere in this "
        "repo (definition and all call sites). Behavior must not change; "
        "run the tests to verify."
    ),
    files={
        "billing.py": (
            "def calc(prices, tax):\n"
            "    return round(sum(prices) * (1 + tax), 2)\n"
        ),
        "invoice.py": (
            "from billing import calc\n\n\n"
            "def invoice_total(prices):\n"
            "    return calc(prices, 0.2)\n"
        ),
        "test_invoice.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_total(self):\n"
            "        self.assertEqual(invoice_total([10, 5]), 18.0)\n",
            imports="from invoice import invoice_total\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_renamed(self):\n"
            "        from billing import calculate_total\n"
            "        self.assertEqual(calculate_total([10], 0.0), 10.0)\n"
            "    def test_old_name_gone(self):\n"
            "        src = open('billing.py').read() + open('invoice.py').read()\n"
            "        self.assertNotIn('def calc(', src)\n"
            "        self.assertNotIn('calc(prices, 0.2)', src)\n"
            "    def test_behavior(self):\n"
            "        from invoice import invoice_total\n"
            "        self.assertEqual(invoice_total([10, 5]), 18.0)\n",
        ),
    },
)

_t(
    id="ref-extract-constant",
    category="refactor",
    prompt=(
        "The tax rate 0.0825 appears as a magic number in two functions in "
        "shop.py. Extract it into a module-level constant TAX_RATE and use "
        "it in both places. Behavior must not change; run the tests to verify."
    ),
    files={
        "shop.py": (
            "def with_tax(price):\n"
            "    return round(price * (1 + 0.0825), 2)\n\n\n"
            "def tax_amount(price):\n"
            "    return round(price * 0.0825, 2)\n"
        ),
        "test_shop.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_with_tax(self):\n"
            "        self.assertEqual(with_tax(100), 108.25)\n"
            "    def test_tax_amount(self):\n"
            "        self.assertEqual(tax_amount(100), 8.25)\n",
            imports="from shop import with_tax, tax_amount\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_constant(self):\n"
            "        import shop\n"
            "        self.assertEqual(shop.TAX_RATE, 0.0825)\n"
            "    def test_no_magic_number_in_functions(self):\n"
            "        import ast, inspect, shop\n"
            "        for fn in (shop.with_tax, shop.tax_amount):\n"
            "            tree = ast.parse(inspect.getsource(fn))\n"
            "            nums = [n.value for n in ast.walk(tree)\n"
            "                    if isinstance(n, ast.Constant) and n.value == 0.0825]\n"
            "            self.assertEqual(nums, [], f'magic number still in {fn.__name__}')\n"
            "    def test_behavior(self):\n"
            "        from shop import with_tax, tax_amount\n"
            "        self.assertEqual(with_tax(100), 108.25)\n"
            "        self.assertEqual(tax_amount(100), 8.25)\n",
        ),
    },
)

_t(
    id="ref-remove-dead-code",
    category="refactor",
    prompt=(
        "report.py contains an unused function old_format_row left over from "
        "a refactor. Remove it (and only it). The tests must still pass; run "
        "them to verify."
    ),
    files={
        "report.py": (
            "def old_format_row(row):\n"
            "    return ' | '.join(str(c) for c in row)\n\n\n"
            "def format_row(row):\n"
            "    return ', '.join(str(c) for c in row)\n\n\n"
            "def format_report(rows):\n"
            "    return '\\n'.join(format_row(r) for r in rows)\n"
        ),
        "test_report.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_report(self):\n"
            "        self.assertEqual(format_report([[1, 2], [3, 4]]), '1, 2\\n3, 4')\n",
            imports="from report import format_report\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_gone(self):\n"
            "        self.assertNotIn('old_format_row', open('report.py').read())\n"
            "    def test_behavior(self):\n"
            "        from report import format_report\n"
            "        self.assertEqual(format_report([[1, 2]]), '1, 2')\n",
        ),
    },
)

_t(
    id="ref-bare-except",
    category="refactor",
    prompt=(
        "loader.py uses bare `except:` clauses, which swallow KeyboardInterrupt "
        "and SystemExit. Change every bare except to `except Exception:` "
        "without otherwise altering behavior. Run the tests to verify."
    ),
    files={
        "loader.py": (
            "import json\n\n\n"
            "def load_json(text):\n"
            "    try:\n"
            "        return json.loads(text)\n"
            "    except:\n"
            "        return None\n\n\n"
            "def load_int(text):\n"
            "    try:\n"
            "        return int(text)\n"
            "    except:\n"
            "        return 0\n"
        ),
        "test_loader.py": _unittest(
            "class T(unittest.TestCase):\n"
            "    def test_json(self):\n"
            "        self.assertEqual(load_json('{\"a\": 1}'), {'a': 1})\n"
            "        self.assertIsNone(load_json('nope'))\n"
            "    def test_int(self):\n"
            "        self.assertEqual(load_int('7'), 7)\n"
            "        self.assertEqual(load_int('x'), 0)\n",
            imports="from loader import load_json, load_int\n",
        ),
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_no_bare_except(self):\n"
            "        import ast\n"
            "        tree = ast.parse(open('loader.py').read())\n"
            "        bare = [h for h in ast.walk(tree)\n"
            "                if isinstance(h, ast.ExceptHandler) and h.type is None]\n"
            "        self.assertEqual(bare, [])\n"
            "    def test_behavior(self):\n"
            "        from loader import load_json, load_int\n"
            "        self.assertIsNone(load_json('nope'))\n"
            "        self.assertEqual(load_int('x'), 0)\n",
        ),
    },
)

# --------------------------------------------------------------------------
# E. Build from scratch — spec in the prompt, data provided
# --------------------------------------------------------------------------

_t(
    id="new-csv-stats",
    category="scratch",
    prompt=(
        "Write csv_stats.py: when run with `python3 csv_stats.py data.csv`, "
        "it prints exactly one line `rows=<N> mean_price=<M>` where N is the "
        "number of data rows and M the mean of the price column formatted "
        "with two decimals. Verify it against data.csv (expected: rows=4 "
        "mean_price=2.50)."
    ),
    files={
        "data.csv": "name,price\napple,1.00\nbread,2.50\ncheese,4.00\ndates,2.50\n",
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_output(self):\n"
            "        out = subprocess.run([sys.executable, 'csv_stats.py', 'data.csv'],\n"
            "                             capture_output=True, text=True)\n"
            "        self.assertEqual(out.returncode, 0, out.stderr)\n"
            "        self.assertEqual(out.stdout.strip(), 'rows=4 mean_price=2.50')\n",
            imports="import subprocess\nimport sys\n",
        ),
    },
)

_t(
    id="new-json-to-csv",
    category="scratch",
    prompt=(
        "Write convert.py: when run with `python3 convert.py`, it reads "
        "input.json (a list of objects with id and name keys) and writes "
        "out.csv with header line `id,name` followed by one row per object, "
        "sorted by id ascending. Verify by running it and checking out.csv."
    ),
    files={
        "input.json": '[{"id": 3, "name": "carol"}, {"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]\n',
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_csv(self):\n"
            "        r = subprocess.run([sys.executable, 'convert.py'], capture_output=True, text=True)\n"
            "        self.assertEqual(r.returncode, 0, r.stderr)\n"
            "        rows = [l.strip() for l in open('out.csv') if l.strip()]\n"
            "        self.assertEqual(rows, ['id,name', '1,alice', '2,bob', '3,carol'])\n",
            imports="import subprocess\nimport sys\n",
        ),
    },
)

_t(
    id="new-wordcount-cli",
    category="scratch",
    prompt=(
        "Write wordcount.py: `python3 wordcount.py sample.txt` prints exactly "
        "`<lines> <words> <chars>` (single spaces) where chars is the file "
        "size in bytes. Verify it against sample.txt."
    ),
    files={
        "sample.txt": "the quick brown fox\njumps over\nthe lazy dog\n",
    },
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_counts(self):\n"
            "        r = subprocess.run([sys.executable, 'wordcount.py', 'sample.txt'],\n"
            "                           capture_output=True, text=True)\n"
            "        self.assertEqual(r.returncode, 0, r.stderr)\n"
            "        self.assertEqual(r.stdout.split(), ['3', '9', '44'])\n",
            imports="import subprocess\nimport sys\n",
        ),
    },
)

_t(
    id="new-utils-package",
    category="scratch",
    prompt=(
        "Create a utils package (directory with __init__.py) exposing "
        "slugify(text): lowercase the text, replace every run of "
        "non-alphanumeric characters with a single hyphen, and strip leading/"
        "trailing hyphens. `from utils import slugify` must work; "
        "slugify('Hello, World!') == 'hello-world'. Write a quick test and "
        "run it to verify."
    ),
    files={},
    verify_files={
        "_verify.py": _unittest(
            "class V(unittest.TestCase):\n"
            "    def test_basic(self):\n"
            "        self.assertEqual(slugify('Hello, World!'), 'hello-world')\n"
            "    def test_runs(self):\n"
            "        self.assertEqual(slugify('  a  b//c  '), 'a-b-c')\n"
            "    def test_clean(self):\n"
            "        self.assertEqual(slugify('Already-Clean'), 'already-clean')\n",
            imports="from utils import slugify\n",
        ),
    },
)

assert len(TASKS) == 30, f"expected 30 tasks, have {len(TASKS)}"
assert len({t.id for t in TASKS}) == 30, "duplicate task ids"


def get_tasks(only: list[str] | None = None) -> list[Task]:
    if not only:
        return list(TASKS)
    by_id = {t.id: t for t in TASKS}
    return [by_id[i] for i in only]
