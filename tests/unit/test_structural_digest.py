"""Scheme-2 approval binding (ADR-0045): built against the dangerous direction.

The dangerous failure is "behaviour changed and the approval stayed valid". Every behaviour edit
below must change the digest; only comments, layout and (where nothing reads them) docstrings
may leave it unchanged. Anything the digest cannot classify must fall back to exact bytes.
"""

from __future__ import annotations

import ast
import hashlib
import io
import keyword
import re
import shutil
import subprocess
import sys
import textwrap
import tokenize
from collections.abc import Iterator
from pathlib import Path
from types import CodeType
from typing import Any

import pytest

from alpha_cli import _structural_digest as digest_module
from alpha_cli._structural_digest import (
    StructuralDigestError,
    binding_digest,
    file_binding,
    source_binding,
)

ROOT = Path(__file__).resolve().parents[2]


def _digest(source: str) -> str:
    return source_binding(textwrap.dedent(source).encode("utf-8"))[1]


def _mode(source: str) -> str:
    return source_binding(textwrap.dedent(source).encode("utf-8"))[0]


BASE = '''
"""Module docstring."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = ["Detector", "score"]

LIMIT = 10


@dataclass(frozen=True)
class Detector:
    """Class docstring."""

    window: int = 5
    label: str = "pivot"
    tags: list[str] = field(default_factory=list)

    def run(self, values, scale=2.0, *, strict=True):
        """Method docstring."""
        total = 0
        for index, value in enumerate(values[1:-1]):
            if value > self.window and index is not None:
                total += value * scale
            elif value == LIMIT:
                total -= 1
        return f"{self.label}:{total:.2f}"


def score(xs, threshold=0.5):
    def inner(y):
        return y * 3
    return [inner(x) for x in xs if x >= threshold and not math.isnan(x)]
'''


# --- 1. edits that do not change behaviour keep the digest --------------------------------------

UNCHANGED = {
    "comments": BASE.replace("LIMIT = 10", "LIMIT = 10  # the cap  # noqa: E501").replace(
        "        total = 0", "        # running total\n        total = 0  # type: ignore[misc]"
    ),
    "blank lines": BASE.replace("LIMIT = 10\n", "\n\nLIMIT = 10\n\n\n"),
    "trailing comma": BASE.replace(
        '__all__ = ["Detector", "score"]', '__all__ = ["Detector", "score",]'
    ),
    "redundant parentheses": BASE.replace("return y * 3", "return (y * 3)").replace(
        "if value > self.window and", "if (value > self.window) and"
    ),
    "line continuation": BASE.replace(
        "def score(xs, threshold=0.5):", "def score(\n    xs,\n    threshold=0.5,\n):"
    ),
    "quote style": BASE.replace('label: str = "pivot"', "label: str = 'pivot'"),
    "implicit concatenation": BASE.replace('label: str = "pivot"', 'label: str = "pi" "vot"'),
    "docstring edits": BASE.replace("Module docstring.", "A rewritten module docstring.")
    .replace('"""Class docstring."""', '"""Class.\n\n    More words.\n    """')
    .replace('        """Method docstring."""\n', ""),
}


@pytest.mark.parametrize("name", sorted(UNCHANGED))
def test_edits_that_keep_behaviour_keep_the_digest(name: str) -> None:
    assert _mode(BASE) == "structure"
    assert UNCHANGED[name] != BASE
    assert _digest(UNCHANGED[name]) == _digest(BASE)


def test_the_project_formatter_keeps_the_digest_on_a_real_bound_file(tmp_path: Path) -> None:
    source = (ROOT / "packages/alpha-research/src/alpha_research/event_study.py").read_text()
    # Re-render the tree with no comments and different layout, then run the project formatter.
    rendered = tmp_path / "rendered.py"
    rendered.write_text(ast.unparse(ast.parse(source)) + "\n")
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--quiet", "--line-length", "60", str(rendered)],
        check=True,
        cwd=ROOT,
    )
    assert rendered.read_bytes() != source.encode()
    assert source_binding(rendered.read_bytes()) == source_binding(source.encode())


# --- 2. edits that change behaviour change the digest -------------------------------------------

CHANGED = {
    "number": ("LIMIT = 10", "LIMIT = 11"),
    "number type": ("LIMIT = 10", "LIMIT = 10.0"),
    "string": ('label: str = "pivot"', 'label: str = "pivots"'),
    "operator": ("total += value * scale", "total += value / scale"),
    "augmented operator": ("total -= 1", "total += 1"),
    "swapped comparison": ("value > self.window", "self.window > value"),
    "comparison operator": ("x >= threshold", "x > threshold"),
    "default argument": ("threshold=0.5", "threshold=0.25"),
    "reordered arguments": ("def score(xs, threshold=0.5):", "def score(threshold, xs=0.5):"),
    "keyword-only marker": ("scale=2.0, *, strict=True", "scale=2.0, strict=True"),
    "removed line": ("            elif value == LIMIT:\n                total -= 1\n", ""),
    "added statement": ("        total = 0\n", "        total = 0\n        total = 1\n"),
    "decorator": ("@dataclass(frozen=True)", "@dataclass(frozen=False)"),
    "removed decorator": ("@dataclass(frozen=True)\n", ""),
    "renamed variable": ("for index, value in", "for position, value in"),
    "renamed function": ("def inner(y):", "def inner2(y):"),
    "import": ("import math\n", "import cmath as math\n"),
    "from import": (
        "from dataclasses import dataclass, field", "from attrs import dataclass, field"
    ),
    "future import": ("from __future__ import annotations\n", ""),
    "__all__": ('__all__ = ["Detector", "score"]', '__all__ = ["Detector"]'),
    "runtime annotation": ("window: int = 5", "window: float = 5"),
    "dataclass field": ("tags: list[str] = field(default_factory=list)", "tags: list[str] = []"),
    "f-string": ('f"{self.label}:{total:.2f}"', 'f"{self.label}:{total:.3f}"'),
    "f-string conversion": ('f"{self.label}:', 'f"{self.label!r}:'),
    "keyword argument": ("default_factory=list", "default_factory=tuple"),
    "keyword value": ("frozen=True", "frozen=1"),
    "is versus ==": ("index is not None", "index != None"),
    "boolean operator": ("and not math.isnan(x)", "or not math.isnan(x)"),
    "negation": ("and not math.isnan(x)", "and math.isnan(x)"),
    "slice off by one": ("values[1:-1]", "values[1:-2]"),
    "slice start": ("values[1:-1]", "values[0:-1]"),
    "nested function constant": ("return y * 3", "return y * 4"),
    "class attribute": ("window: int = 5", "window: int = 6"),
    "statement order": (
        "LIMIT = 10\n",
        "LIMIT = 10\n",
    ),  # replaced below by a true reorder
    "constant folding": ("LIMIT = 10", "LIMIT = 5 + 5"),
    "negative literal": ("threshold=0.5", "threshold=-0.5"),
    "unary versus binary": ("total -= 1", "total += -1"),
    "string prefix": ('label: str = "pivot"', 'label: str = b"pivot"'),
    "loop target": (
        "for index, value in enumerate", "for value, index in enumerate"
    ),
    "return value": ("        return f\"{self.label}", "        return None or f\"{self.label}"),
    "elif to if": ("            elif value == LIMIT:", "            if value == LIMIT:"),
}  # fmt: skip
CHANGED["statement order"] = (
    "LIMIT = 10\n\n\n@dataclass",
    "@dataclass",
)


def _reordered() -> str:
    # Move LIMIT below the class: same statements, different order.
    without = BASE.replace("LIMIT = 10\n", "", 1)
    return without + "\nLIMIT = 10\n"


@pytest.mark.parametrize("name", sorted(CHANGED))
def test_every_behaviour_edit_changes_the_digest(name: str) -> None:
    old, new = CHANGED[name]
    edited = _reordered() if name == "statement order" else BASE.replace(old, new, 1)
    assert edited != BASE, name
    ast.parse(textwrap.dedent(edited))  # each edit is still valid Python
    assert _digest(edited) != _digest(BASE), name


def test_the_digest_is_computed_before_any_constant_folding() -> None:
    assert _digest("x = 1 + 2\n") != _digest("x = 3\n")
    assert _digest("x = -1\n") != _digest("x = 0 - 1\n")
    assert _digest("x = 'a' * 2\n") != _digest("x = 'aa'\n")
    assert _digest("x = (1, 2)\n") != _digest("x = [1, 2]\n")


def test_literals_keep_their_exact_types_and_values() -> None:
    values = ["1", "1.0", "True", "1j", "'1'", "b'1'", "None", "...", "0.1", "0.10000000000000002"]
    digests = {_digest(f"x = {value}\n") for value in values}
    assert len(digests) == len(values)


# --- docstrings that can be read stay bound -----------------------------------------------------


@pytest.mark.parametrize(
    "reader",
    [
        "print(__doc__)",
        "x = getattr(f, '__doc__')",
        "import pydantic",
        "from pydantic import BaseModel",
        "import typer",
        "import click",
        "import pydoc",
        "import doctest",
        "help(f)",
        "from inspect import getdoc",
    ],
)
def test_a_file_that_can_read_docstrings_keeps_them(reader: str) -> None:
    source = f'"""Doc."""\n{reader}\n\ndef f():\n    """One."""\n    return 1\n'
    edited = source.replace('"""One."""', '"""Two."""')
    assert _mode(source) in {"structure-with-docstrings", "bytes"}
    assert _digest(edited) != _digest(source)


def test_only_a_leading_string_statement_is_a_docstring() -> None:
    source = 'def f():\n    x = 1\n    "not a docstring"\n    return x\n'
    assert _digest(source) != _digest(source.replace("not a docstring", "changed"))
    # An f-string or bytes literal in docstring position is not a docstring either.
    assert _digest('def f():\n    f"{1}"\n') != _digest('def f():\n    f"{2}"\n')
    assert _digest("def f():\n    b'x'\n") != _digest("def f():\n    b'y'\n")
    # A body that is only a docstring is not the same as a body that does something.
    assert _digest('def f():\n    "doc"\n') != _digest("def f():\n    pass\n")


# --- code that reads its own layout is bound by bytes -------------------------------------------


@pytest.mark.parametrize(
    "reader",
    [
        "import inspect",
        "from inspect import getsource",
        "import linecache",
        "import traceback",
        "x = f.__code__.co_firstlineno",
        "import sys\nx = sys._getframe().f_lineno",
        "x = getattr(f, '__code__')",
        "x = record.lineno",
    ],
)
def test_a_file_that_reads_source_or_line_numbers_is_byte_bound(reader: str) -> None:
    source = f"{reader}\n\ndef f():\n    return 1\n"
    assert _mode(source) == "bytes"
    assert _digest(source + "# a comment\n") != _digest(source)
    assert _digest(source + "\n\n") != _digest(source)


# --- 4. fail closed -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [b"def f(:\n", b"x = 1\x00\n", b"\xff\xfe not text", b"x = (" * 400 + b")" * 400 + b"\n"],
)
def test_source_that_does_not_parse_is_bound_by_bytes(raw: bytes) -> None:
    mode, value = source_binding(raw)
    assert (mode, value) == ("bytes", hashlib.sha256(raw).hexdigest())


def test_an_unknown_syntax_node_falls_back_to_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"x = 1\n"
    known = digest_module._KNOWN_NODES - {"Assign"}
    monkeypatch.setattr(digest_module, "_KNOWN_NODES", known)
    assert source_binding(raw) == ("bytes", hashlib.sha256(raw).hexdigest())


def test_an_unknown_constant_type_falls_back_to_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"x = 1\n"
    real_parse = ast.parse

    def parse_with_foreign_constant(source: bytes, **kwargs: Any) -> ast.AST:
        tree: ast.AST = real_parse(source, **kwargs)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                setattr(node, "value", frozenset({1}))  # noqa: B010 - bypass the stub type
        return tree

    monkeypatch.setattr(ast, "parse", parse_with_foreign_constant)
    assert source_binding(raw) == ("bytes", hashlib.sha256(raw).hexdigest())


def test_another_python_minor_version_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(digest_module, "SUPPORTED_PYTHON", (3, 13))
    with pytest.raises(StructuralDigestError, match="refusing"):
        source_binding(b"x = 1\n")
    target = tmp_path / "m.py"
    target.write_text("x = 1\n")
    with pytest.raises(StructuralDigestError, match="refusing"):
        binding_digest({"m.py": target})


def test_warning_filters_cannot_change_the_mode() -> None:
    raw = b"x = '\\d'\n"  # an invalid escape raises SyntaxWarning while parsing
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        strict = source_binding(raw)
    assert strict == source_binding(raw)
    assert strict[0] == "structure"


def test_missing_files_refuse_and_links_bind_their_content(tmp_path: Path) -> None:
    real = tmp_path / "real.py"
    real.write_text("x = 1\n")
    link = tmp_path / "link.py"
    link.symlink_to(real)
    assert file_binding(link) == file_binding(real)  # as the byte digest did; callers forbid links
    dangling = tmp_path / "dangling.py"
    dangling.symlink_to(tmp_path / "absent.py")
    for path in (tmp_path / "absent.py", dangling, tmp_path):
        with pytest.raises(StructuralDigestError):
            file_binding(path)
    with pytest.raises(StructuralDigestError):
        binding_digest({})


# --- the composite binds labels, modes, non-Python bytes and its own rules ----------------------


def test_the_composite_binds_labels_modes_other_files_and_the_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = tmp_path / "m.py"
    code.write_text("x = 1\n")
    data = tmp_path / "theme.json"
    data.write_text('{"a": 1}\n')
    files = {"m.py": code, "theme.json": data}
    first = binding_digest(files)
    assert binding_digest({"n.py": code, "theme.json": data}) != first
    assert file_binding(data) == {
        "mode": "bytes",
        "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
    }
    data.write_text('{"a": 1}\n\n')  # whitespace in a non-Python file is still bound
    assert binding_digest(files) != first
    data.write_text('{"a": 1}\n')
    code.write_text("x = 1  # comment\n")
    assert binding_digest(files) == first
    monkeypatch.setattr(digest_module, "_own_bytes_sha256", lambda: "0" * 64)
    assert binding_digest(files) != first


# --- 3. property: every mutant of a real bound module that changes behaviour changes the digest -


def _bound_files() -> list[Path]:
    from alpha_cli._native_loop_admission import WORKER, WORKER_FILES
    from alpha_cli._native_rule_environment import COSTED_FILES, DAILY_GUARD_FILES, RULE_FILES

    cli = ROOT / "apps/alpha-cli/src/alpha_cli"
    research = sorted((ROOT / "packages/alpha-research/src/alpha_research").rglob("*.py"))
    modules = [
        cli / name
        for name in (
            "research_intake.py",
            "research_runtime.py",
            "research_crypto_data.py",
            "research_crypto_runtime.py",
            *DAILY_GUARD_FILES,
        )
    ]
    worker = sorted(
        {
            WORKER / name
            for name in (*WORKER_FILES, *RULE_FILES, *COSTED_FILES)
            if name.endswith(".py")
        }
        | {WORKER / "daily_container_entry.py"}
    )
    return [*research, *modules, *worker]


_SWAPS = {
    "+": "-", "-": "+", "*": "/", "/": "*", "//": "/", "%": "*", "**": "*", "<": "<=",
    "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "==", "<<": ">>", ">>": "<<", "&": "|",
    "|": "&", "^": "&", "+=": "-=", "-=": "+=", "*=": "/=", "and": "or", "or": "and",
    "is": "==", "in": "not in", "True": "False", "False": "True", "None": "0", "break": "continue",
    "continue": "break", "not": "", "return": "return None or", "-1": "-2",
}  # fmt: skip


Edit = tuple[str, int, int, str]  # (kind, start, end, replacement) on the source text


def _edits(source: str) -> Iterator[Edit]:
    """Token-level edits, the way a mutation tool edits text (applied lazily: files are big)."""
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def at(position: tuple[int, int]) -> int:
        return offsets[position[0] - 1] + position[1]

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        start, end = at(token.start), at(token.end)
        text = token.string
        if token.type == tokenize.NUMBER:
            digits = text.replace("_", "")
            yield "behaviour", start, end, str(int(digits) + 1) if digits.isdigit() else text + "1"
        elif token.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE):
            cut = start
            if token.type == tokenize.STRING:
                quote = min(i for i in (text.find("'"), text.find('"')) if i >= 0)
                cut += quote + (3 if text[quote : quote + 3] in ("'''", '"""') else 1)
            yield "behaviour", cut, cut, "Q"
        elif text in _SWAPS and token.type in (tokenize.OP, tokenize.NAME):
            yield "behaviour", start, end, _SWAPS[text]
        elif token.type == tokenize.NAME and not keyword.iskeyword(text):
            yield "behaviour", end, end, "_m"
        elif token.type == tokenize.NEWLINE:
            yield "cosmetic", start, start, "  # mutant comment"
            yield "cosmetic", end, end, "\n"
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield "behaviour", offsets[index], offsets[index + 1], ""
            yield "behaviour", offsets[index], offsets[index], line


def _normal(code: CodeType) -> CodeType:
    consts = tuple(_normal(c) if isinstance(c, CodeType) else c for c in code.co_consts)
    return code.replace(co_firstlineno=1, co_linetable=b"", co_filename="m", co_consts=consts)


def _strip_docstrings(tree: ast.Module) -> ast.Module:
    # Written independently of the digest: drop a leading str statement, keep bodies non-empty.
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.fix_missing_locations(tree)


def _bytecode(source: str, *, docstrings: bool) -> CodeType | None:
    """The independent oracle: compiled, line-number-free bytecode (asserts kept)."""
    try:
        tree = ast.parse(source)
        if not docstrings:
            tree = _strip_docstrings(tree)
        return _normal(compile(tree, "m", "exec", dont_inherit=True, optimize=0))
    except (SyntaxError, ValueError):
        return None


def _sample(items: list[Edit], cap: int) -> list[Edit]:
    step = max(1, len(items) // cap)
    return items[::step][:cap]


def _sweep(files: list[Path], cap: int) -> dict[str, int]:
    counts = dict.fromkeys(
        (
            "files",
            "mutants",
            "unparsable",
            "behaviour",
            "caught",
            "equivalent",
            "cosmetic",
            "cosmetic_kept",
        ),
        0,
    )
    for path in files:
        source = path.read_text()
        original_mode, original = source_binding(source.encode())
        docstrings = original_mode != "structure"
        reference = _bytecode(source, docstrings=docstrings)
        assert reference is not None, path
        counts["files"] += 1
        for kind, start, end, replacement in _sample(list(_edits(source)), cap):
            mutant = source[:start] + replacement + source[end:]
            counts["mutants"] += 1
            code = _bytecode(mutant, docstrings=docstrings)
            if code is None:
                counts["unparsable"] += 1
                continue
            mode, value = source_binding(mutant.encode())
            if kind == "cosmetic":
                assert code == reference, (path, "cosmetic mutant changed bytecode")
                counts["cosmetic"] += 1
                counts["cosmetic_kept"] += value == original
                if original_mode != "bytes":
                    assert value == original, (path, "cosmetic edit changed digest")
                continue
            if code != reference:
                # The independent oracle (compiled bytecode) says behaviour changed.
                counts["behaviour"] += 1
                assert value != original, (path, "behaviour changed but the digest did not")
                counts["caught"] += 1
            else:
                # Same bytecode: only an unread docstring or a folded constant differs.
                counts["equivalent"] += 1
    return counts


def test_every_behaviour_changing_mutant_of_research_code_changes_the_digest() -> None:
    research = [path for path in _bound_files() if "alpha_research" in path.parts]
    counts = _sweep(research, cap=6)
    print(f"mutation sweep (research tree, 6 per file): {counts}")
    assert counts["files"] >= 30
    assert counts["behaviour"] >= 60
    assert counts["caught"] == counts["behaviour"]


@pytest.mark.slow_oracle
def test_every_behaviour_changing_mutant_of_all_bound_code_changes_the_digest() -> None:
    counts = _sweep(_bound_files(), cap=60)
    print(f"mutation sweep (all bound files, 60 per file): {counts}")
    assert counts["files"] >= 70
    assert counts["behaviour"] >= 2500
    assert counts["caught"] == counts["behaviour"]


# --- 5. scheme 1 is frozen and is never satisfied by structure ----------------------------------


def _copy_research_code(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    from alpha_cli import research_cmds

    research_root, modules = research_cmds._research_code_paths()
    root = tmp_path / "alpha_research"
    shutil.copytree(research_root, root, ignore=shutil.ignore_patterns("__pycache__"))
    copies = {}
    for name, path in modules.items():
        copies[name] = tmp_path / path.name
        shutil.copyfile(path, copies[name])
    return root, copies


def test_scheme_one_is_the_exact_pre_adr_byte_formula() -> None:
    import json

    from alpha_cli import research_cmds

    research_root, modules = research_cmds._research_code_paths()

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    tree = {
        p.relative_to(research_root).as_posix(): sha(p)
        for p in sorted(research_root.rglob("*.py"))
        if p.is_file()
    }
    document = {
        "alpha_research": hashlib.sha256(
            json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        **{name: sha(path) for name, path in modules.items()},
    }
    expected = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert research_cmds._byte_code_hash() == expected
    assert research_cmds._implementation_hashes()["code"] != expected


def test_each_scheme_verifies_only_what_it_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import research_cmds

    root, modules = _copy_research_code(tmp_path)
    monkeypatch.setattr(research_cmds, "_research_code_paths", lambda: (root, modules))
    current = research_cmds._implementation_hashes()
    scheme_one = {**current, "code": research_cmds._byte_code_hash()}
    scheme_two = dict(current)
    assert scheme_one["code"] != scheme_two["code"]
    assert not research_cmds._implementation_drifted(scheme_one)
    assert not research_cmds._implementation_drifted(scheme_two)
    assert research_cmds._approved_code_scheme(scheme_one["code"], current) == 1
    assert research_cmds._approved_code_scheme(scheme_two["code"], current) == 2

    # A comment-only edit to a real bound module: scheme 2 holds, scheme 1 does not.
    bound = root / "event_study.py"
    original = bound.read_bytes()
    bound.write_bytes(original + b"\n# a comment that changes no behaviour\n")
    assert research_cmds._implementation_drifted(scheme_one)
    assert not research_cmds._implementation_drifted(scheme_two)
    assert research_cmds._approved_code_scheme(scheme_one["code"], current) is None

    # A behaviour edit: both are invalid.
    text = original.decode()
    assert "return" in text
    bound.write_text(text.replace("return", "return None or", 1))
    assert research_cmds._implementation_drifted(scheme_one)
    assert research_cmds._implementation_drifted(scheme_two)

    # Restoring the exact bytes restores both.
    bound.write_bytes(original)
    assert not research_cmds._implementation_drifted(scheme_one)
    assert not research_cmds._implementation_drifted(scheme_two)

    # Non-Python files in the research tree are bound by bytes under scheme 2.
    theme = next(root.rglob("*.json"))
    theme.write_bytes(theme.read_bytes() + b"\n")
    assert research_cmds._implementation_drifted(scheme_two)
    assert not research_cmds._implementation_drifted(scheme_one)  # scheme 1 never bound them


def test_an_approval_is_only_valid_for_one_of_the_two_exact_schemes() -> None:
    from alpha_cli import research_cmds

    current = research_cmds._implementation_hashes()
    assert research_cmds._approved_code_scheme("0" * 64, current) is None
    assert research_cmds._approved_code_scheme(None, current) is None
    other = {**current, "evaluator": "0" * 64}
    assert research_cmds._implementation_drifted(other)


# --- docstring and source readers elsewhere in the repository must not read bound code --------

_READERS = ("__doc__", "getdoc(", "getsource", "getcomments", "co_firstlineno", "linecache",
            "model_json_schema", "vars(", ".__dict__", "co_consts", "gi_frame", "cr_frame",
            "_current_frames")  # fmt: skip
_COMMAND_WRAP = re.compile(r"\.(command|callback)\([^)]*\)\(")
_REVIEWED_READERS = {
    # Each reads only its own module docstring or its own (unbound) models.
    "apps/alpha-cli/src/alpha_cli/codex_investigation.py",
    "apps/alpha-cli/src/alpha_cli/native_qlib_pipeline.py",
    "apps/alpha-cli/src/alpha_cli/native_stock_inspect.py",
    "workers/rdagent/install_stock_profile.py",
    "workers/rdagent/qualify_daily_container.py",
    "workers/rdagent/model_gateway.py",  # own module docstring as argparse help; vars(args)
    # vars()/__dict__ of dataclass instances (instance fields, never a class or module docstring).
    "apps/alpha-cli/src/alpha_cli/backtest_cmds.py",
    "apps/alpha-cli/src/alpha_cli/optim_cmds.py",
    "apps/alpha-cli/src/alpha_cli/propfirm_cmds.py",
    "apps/alpha-cli/src/alpha_cli/validate_cmds.py",
    # Registers typer commands (typer reads their docstrings) from local_pdf_cmds,
    # native_stock_cmds, validate_cmds and report_cmds; none of them is bound.
    "apps/alpha-cli/src/alpha_cli/main.py",
    # The digest itself names the readers it guards against.
    "apps/alpha-cli/src/alpha_cli/_structural_digest.py",
}


def test_no_unreviewed_code_reads_docstrings_or_source_of_other_modules() -> None:
    found = set()
    for top in ("apps", "packages", "workers"):
        for path in (ROOT / top).rglob("*.py"):
            parts = path.relative_to(ROOT).parts
            if any(part in {"tests", ".venv", "node_modules", "__pycache__"} for part in parts):
                continue
            text = path.read_text(errors="replace")
            if any(reader in text for reader in _READERS) or _COMMAND_WRAP.search(text):
                found.add(path.relative_to(ROOT).as_posix())
    bound = {path.relative_to(ROOT).as_posix() for path in _bound_files()}
    assert not (found & bound)
    wrapped = {"local_pdf_cmds.py", "native_stock_cmds.py", "validate_cmds.py", "report_cmds.py"}
    assert not wrapped & {path.name for path in _bound_files()}
    assert found == _REVIEWED_READERS


# --- the rule sets are pinned name by name (a dropped name would silently weaken the rules) -----

_EXPECTED_LAYOUT_READERS = (
    "inspect", "linecache", "traceback", "tokenize", "dis", "getsource", "getsourcelines",
    "getsourcefile", "findsource", "getcomments", "getframeinfo", "getouterframes",
    "getinnerframes", "currentframe", "_getframe", "f_lineno", "f_lasti", "f_code", "f_back",
    "co_firstlineno", "co_lines", "co_positions", "co_linetable", "co_lnotab", "tb_lineno",
    "tb_frame", "tb_next", "__code__", "__traceback__", "format_exc", "print_exc",
    "format_exception", "format_tb", "extract_tb", "extract_stack", "format_stack",
    "print_stack", "lineno", "end_lineno", "col_offset", "__loader__", "get_source", "settrace",
    "setprofile", "monitoring", "gi_frame", "cr_frame", "ag_frame", "gi_code", "cr_code",
    "ag_code", "_current_frames", "findCaller", "stack_info", "__file__", "__spec__",
    "__cached__", "get_data",
)  # fmt: skip
_EXPECTED_DOCSTRING_READERS = (
    "__doc__", "getdoc", "pydoc", "doctest", "help", "typer", "click", "pydantic", "fastapi",
    "vars", "__dict__", "globals", "co_consts",
)  # fmt: skip
_NOT_PRODUCED_BY_PARSE = {
    # Abstract bases, mode roots other than ``exec``, and classes kept only for compatibility.
    "AST", "mod", "stmt", "expr", "expr_context", "boolop", "operator", "unaryop", "cmpop",
    "excepthandler", "pattern", "type_ignore", "type_param", "slice", "Expression",
    "Interactive", "FunctionType", "Suite", "TypeIgnore", "AugLoad", "AugStore", "Param",
    "Index", "ExtSlice", "_ast_Ellipsis",
}  # fmt: skip


@pytest.mark.parametrize("name", _EXPECTED_LAYOUT_READERS)
def test_each_layout_reader_name_makes_a_file_byte_bound(name: str) -> None:
    for source in (f"x = {name}\n", f"x = y.{name}\n", f"x = getattr(y, {name!r})\n"):
        assert _mode(source) == "bytes", (name, source)
    assert set(_EXPECTED_LAYOUT_READERS) == digest_module._LAYOUT_READERS


@pytest.mark.parametrize("name", _EXPECTED_DOCSTRING_READERS)
def test_each_docstring_reader_name_keeps_docstrings(name: str) -> None:
    for source in (f"x = {name}\n", f"x = y.{name}\n", f"from {name} import z\n"):
        assert _mode(source) == "structure-with-docstrings", (name, source)
    assert set(_EXPECTED_DOCSTRING_READERS) == digest_module._DOCSTRING_READERS


def test_reader_names_are_found_in_every_position() -> None:
    assert _mode("import a.inspect.b\n") == "bytes"
    assert _mode("import os as inspect\n") == "bytes"
    assert _mode("from a.traceback import b\n") == "bytes"
    assert _mode("f(lineno=1)\n") == "bytes"
    assert _mode("x = 1\n") == "structure"


def test_the_known_nodes_are_exactly_the_python_312_parse_nodes() -> None:
    concrete = {
        name
        for name in dir(ast)
        if isinstance(getattr(ast, name), type) and issubclass(getattr(ast, name), ast.AST)
    } - _NOT_PRODUCED_BY_PARSE
    assert concrete == digest_module._KNOWN_NODES
    seen: set[str] = set()
    for top in ("apps", "packages", "workers", "scripts", "tests"):
        for path in (ROOT / top).rglob("*.py"):
            if ".venv" in path.parts or "node_modules" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_bytes())
            except SyntaxError:
                continue
            seen.update(type(node).__name__ for node in ast.walk(tree))
    assert seen <= digest_module._KNOWN_NODES


def test_an_unexpected_field_value_falls_back_to_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"from . import x\n"
    real_parse = ast.parse

    def parse_with_float_level(source: bytes, **kwargs: Any) -> ast.AST:
        tree: ast.AST = real_parse(source, **kwargs)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                setattr(node, "level", 1.5)  # noqa: B010 - bypass the stub type
        return tree

    monkeypatch.setattr(ast, "parse", parse_with_float_level)
    assert source_binding(raw) == ("bytes", hashlib.sha256(raw).hexdigest())


def test_match_singletons_and_relative_imports_are_bound() -> None:
    base = "match x:\n    case True:\n        pass\n"
    assert _digest(base) != _digest(base.replace("True", "False"))
    assert _digest(base) != _digest(base.replace("True", "None"))
    assert _mode(base) == "structure"
    assert _digest("from . import x\n") != _digest("from .. import x\n")
    assert _digest("from . import x\n") != _digest("from .a import x\n")


def test_the_refusal_names_both_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest_module, "SUPPORTED_PYTHON", (3, 13))
    running = f"{sys.version_info[0]}.{sys.version_info[1]}"
    with pytest.raises(StructuralDigestError, match=rf"Python 3\.13; refusing .* {running}$"):
        source_binding(b"x = 1\n")


def test_the_canonical_form_is_pinned() -> None:
    # Any change to the encoding (labels, separators, domain) changes this value; such a change
    # is a new scheme and needs a new ADR, never a silent edit.
    golden = (
        b'"""Doc."""\nx = {"a": b"\\x00", 1: (1.5, 2j, ..., None, True)}\n'
        b"match x:\n    case None:\n        pass\n"
    )
    assert source_binding(golden) == (
        "structure",
        "b513f364206f3e364ec24f23afcdd60fcac14f12b7e8084bc051416910b9eccd",
    )


# --- review findings: ordinary APIs that expose layout or docstrings (each one was a hole) -----

_LAYOUT_CONSTRUCTS = {
    "own source via __file__": "from pathlib import Path\nTEXT = Path(__file__).read_text()\n",
    "loader source": "TEXT = __loader__.get_source(__name__)\n",
    "generator frame": "def g():\n    yield 1\nX = repr(g().gi_frame)\n",
    "generator code": "def g():\n    yield 1\nX = str(g().gi_code)\n",
    "coroutine frame": "async def c():\n    pass\nX = c().cr_frame\n",
    "all thread frames": "import sys\nX = repr(sys._current_frames())\n",
    "obscured frame access": "import sys\nX = getattr(sys, '_get' + 'frame')(0)\n",
    "obscured line number": "X = getattr(f, 'f_' + 'lineno')\n",
    "computed lookup on builtins": "import builtins\nX = getattr(builtins, NAME)\n",
    "log format with line": "FORMAT = '%(name)s:%(lineno)d'\n",
    "log format with function": "FORMAT = '%(funcName)s'\n",
    "logging module": "import logging\nlogging.warning('x')\n",
    "warnings module": "import warnings\nwarnings.warn('w')\n",
    "warn import": "from warnings import warn\nwarn('w')\n",
    "eval": "X = eval('1')\n",
    "exec": "exec('x = 1')\n",
    "compile builtin": "C = compile('1', 'f', 'eval')\n",
    "dynamic import": "M = __import__('os')\n",
    "logging caller": "X = logger.findCaller()\n",
    "stack info": "logger.info('x', stack_info=True)\n",
}
_DOCSTRING_CONSTRUCTS = {
    "vars of a class": "class A:\n    'alpha'\nX = vars(A).get('_' + '_doc__')\n",
    "class __dict__": "class A:\n    'alpha'\nX = A.__dict__\n",
    "module globals": "'alpha'\nX = globals()\n",
    "function constants": "def f():\n    'alpha'\nX = f.co_consts\n",
    "computed getattr": "class A:\n    'alpha'\nX = getattr(A, NAME)\n",
    "computed hasattr": "class A:\n    'alpha'\nX = hasattr(A, NAME)\n",
    "docstring key in a string": "class A:\n    'alpha'\nKEY = 'x__doc__'\n",
}


@pytest.mark.parametrize("name", sorted(_LAYOUT_CONSTRUCTS))
def test_reviewed_layout_readers_are_byte_bound(name: str) -> None:
    source = _LAYOUT_CONSTRUCTS[name]
    assert _mode(source) == "bytes", name
    assert _digest(source) != _digest("\n" + source)


@pytest.mark.parametrize("name", sorted(_DOCSTRING_CONSTRUCTS))
def test_reviewed_docstring_readers_keep_docstrings(name: str) -> None:
    source = _DOCSTRING_CONSTRUCTS[name]
    assert _mode(source) == "structure-with-docstrings", name
    assert _digest(source) != _digest(source.replace("'alpha'", "'beta'"))


def test_ordinary_lookalikes_do_not_force_bytes() -> None:
    # A variable called ``warnings``, ``re.compile`` and a literal getattr stay structural.
    assert _mode("warnings = payload.get('warnings')\n") == "structure"
    assert _mode("import re\nP = re.compile('x')\n") == "structure"
    assert _mode("X = getattr(a, 'b', None)\n") == "structure"
    assert _mode("setattr(a, name, 1)\n") == "structure"
    assert _mode("TIMEFRAME = 'timeframe'\n") == "structure"


@pytest.mark.parametrize(
    "source",
    [
        "def inspect():\n    pass\n",
        "def f(lineno):\n    pass\n",
        "class traceback:\n    pass\n",
        "def f():\n    global monitoring\n",
        "try:\n    pass\nexcept E as linecache:\n    pass\n",
        "match x:\n    case [*lineno]:\n        pass\n",
        "match x:\n    case {**lineno}:\n        pass\n",
        "match x:\n    case y as lineno:\n        pass\n",
    ],
)
def test_reader_names_are_found_in_binding_positions(source: str) -> None:
    assert _mode(source) == "bytes"
