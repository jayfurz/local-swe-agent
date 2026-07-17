from swea.tools import (
    MAX_OUTPUT_CHARS,
    bash_impl,
    edit_file_impl,
    glob_files_impl,
    grep_impl,
    list_dir_impl,
    read_file_impl,
    write_file_impl,
)


def test_bash_runs_in_workspace(tmp_path):
    out = bash_impl(tmp_path, "echo hello; pwd")
    assert out.startswith("exit code: 0")
    assert "hello" in out
    assert str(tmp_path.resolve()) in out


def test_bash_reports_exit_code_and_stderr(tmp_path):
    out = bash_impl(tmp_path, "echo oops >&2; exit 3")
    assert out.startswith("exit code: 3")
    assert "[stderr]" in out and "oops" in out


def test_bash_timeout(tmp_path):
    out = bash_impl(tmp_path, "sleep 5", timeout_s=1)
    assert out == "error: command timed out after 1s"


def test_bash_truncates_long_output(tmp_path):
    out = bash_impl(tmp_path, "yes x | head -c 100000")
    assert len(out) < MAX_OUTPUT_CHARS + 200
    assert "chars truncated" in out


def test_write_then_read_roundtrip(tmp_path):
    assert write_file_impl(tmp_path, "pkg/mod.py", "a = 1\nb = 2\n").startswith("wrote ")
    out = read_file_impl(tmp_path, "pkg/mod.py")
    assert "1\ta = 1" in out and "2\tb = 2" in out


def test_read_offset_and_limit(tmp_path):
    write_file_impl(tmp_path, "f.txt", "\n".join(f"line{i}" for i in range(1, 11)))
    out = read_file_impl(tmp_path, "f.txt", offset=4, limit=2)
    assert "line4" in out and "line5" in out and "line3" not in out
    assert "10 lines total; showing 4-5" in out


def test_read_missing_file(tmp_path):
    assert read_file_impl(tmp_path, "nope.txt").startswith("error:")


def test_path_escape_rejected(tmp_path):
    for path in ("../outside.txt", "a/../../outside.txt", "/etc/passwd"):
        assert "outside the workspace" in write_file_impl(tmp_path, path, "x"), path
        assert "outside the workspace" in read_file_impl(tmp_path, path), path


def test_edit_file_exact_replace(tmp_path):
    write_file_impl(tmp_path, "f.py", "x = 1\ny = 2\n")
    assert edit_file_impl(tmp_path, "f.py", "y = 2", "y = 3") == "replaced 1 occurrence in f.py"
    assert (tmp_path / "f.py").read_text() == "x = 1\ny = 3\n"


def test_edit_file_not_found_and_ambiguous(tmp_path):
    write_file_impl(tmp_path, "f.py", "a\na\n")
    assert "not found" in edit_file_impl(tmp_path, "f.py", "zzz", "q")
    assert "occurs 2 times" in edit_file_impl(tmp_path, "f.py", "a", "q")
    assert edit_file_impl(tmp_path, "f.py", "a", "q", replace_all=True) == "replaced 2 occurrences in f.py"
    assert (tmp_path / "f.py").read_text() == "q\nq\n"


def test_list_dir_dirs_first(tmp_path):
    (tmp_path / "zdir").mkdir()
    (tmp_path / "afile.txt").write_text("")
    assert list_dir_impl(tmp_path).splitlines() == ["zdir/", "afile.txt"]


def test_glob_skips_noise_dirs(tmp_path):
    write_file_impl(tmp_path, "src/a.py", "")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "b.py").write_text("")
    out = glob_files_impl(tmp_path, "**/*.py")
    assert "src/a.py" in out and ".venv" not in out


def test_grep_finds_matches_with_include(tmp_path):
    write_file_impl(tmp_path, "a.py", "def target():\n    pass\n")
    write_file_impl(tmp_path, "b.txt", "target here too\n")
    out = grep_impl(tmp_path, r"target", include="*.py")
    assert "a.py:1: def target():" in out and "b.txt" not in out


def test_grep_bad_regex(tmp_path):
    assert grep_impl(tmp_path, "(unclosed").startswith("error: invalid regex")
