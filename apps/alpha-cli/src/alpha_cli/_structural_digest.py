"""Scheme-2 approval binding: a digest of what Python source does, not of its bytes (ADR-0045).

The digest ignores comments, blank lines, formatting, parenthesisation and (where nothing can
read them) docstrings; it binds every other part of the parsed tree: names, literals with their
types, operators, decorators, defaults, annotations, imports and statement order. It is computed
from Python 3.12's unoptimised syntax tree, so constant folding never enters it, and it refuses to
run on any other Python minor version.

Fail closed, per file:

- a file that does not parse, or holds a node or constant this module does not know, is bound
  by its exact bytes;
- a file that names any source, line-number or frame introspection (``inspect``,
  ``linecache``, ``traceback``, ``co_firstlineno``, ...) is bound by its exact bytes, because
  for such code layout can be behaviour;
- a file that names any docstring reader (``__doc__``, ``pydantic``, ``typer``, ...) keeps its
  docstrings in the digest;
- non-Python files are bound by their exact bytes.

The composite digest also binds this module's own bytes, so any change to these rules
invalidates every scheme-2 approval. Standard library only.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

SCHEME: Final = "alpha-python-structure-v1"
SUPPORTED_PYTHON: Final = (3, 12)

Mode = Literal["structure", "structure-with-docstrings", "bytes"]

# Every concrete syntax-tree class Python 3.12 produces. Anything else fails closed.
_KNOWN_NODES: Final = frozenset(
    {
        "Add", "And", "AnnAssign", "Assert", "Assign", "AsyncFor", "AsyncFunctionDef",
        "AsyncWith", "Attribute", "AugAssign", "Await", "BinOp", "BitAnd", "BitOr", "BitXor",
        "BoolOp", "Break", "Call", "ClassDef", "Compare", "Constant", "Continue", "Del",
        "Delete", "Dict", "DictComp", "Div", "Eq", "ExceptHandler", "Expr", "FloorDiv", "For",
        "FormattedValue", "FunctionDef", "GeneratorExp", "Global", "Gt", "GtE", "If", "IfExp",
        "Import", "ImportFrom", "In", "Invert", "Is", "IsNot", "JoinedStr", "LShift", "Lambda",
        "List", "ListComp", "Load", "Lt", "LtE", "MatMult", "Match", "MatchAs", "MatchClass",
        "MatchMapping", "MatchOr", "MatchSequence", "MatchSingleton", "MatchStar", "MatchValue",
        "Mod", "Module", "Mult", "Name", "NamedExpr", "Nonlocal", "Not", "NotEq", "NotIn", "Or",
        "ParamSpec", "Pass", "Pow", "RShift", "Raise", "Return", "Set", "SetComp", "Slice",
        "Starred", "Store", "Sub", "Subscript", "Try", "TryStar", "Tuple", "TypeAlias",
        "TypeVar", "TypeVarTuple", "UAdd", "USub", "UnaryOp", "While", "With", "Yield",
        "YieldFrom", "alias", "arg", "arguments", "comprehension", "keyword", "match_case",
        "withitem",
    }
)  # fmt: skip

# Names that read source text, comments, line numbers or frames, or that run code built at run
# time: such a file stays byte-bound. Matched in every name position and as an exact string.
_LAYOUT_READERS: Final = frozenset(
    {
        "inspect", "linecache", "traceback", "tokenize", "dis", "getsource", "getsourcelines",
        "getsourcefile", "findsource", "getcomments", "getframeinfo", "getouterframes",
        "getinnerframes", "currentframe", "_getframe", "f_lineno", "f_lasti", "f_code",
        "f_back", "co_firstlineno", "co_lines", "co_positions", "co_linetable", "co_lnotab",
        "tb_lineno", "tb_frame", "tb_next", "__code__", "__traceback__", "format_exc",
        "print_exc", "format_exception", "format_tb", "extract_tb", "extract_stack",
        "format_stack", "print_stack", "lineno", "end_lineno", "col_offset", "__loader__",
        "get_source", "settrace", "setprofile", "monitoring", "gi_frame", "cr_frame",
        "ag_frame", "gi_code", "cr_code", "ag_code", "_current_frames", "findCaller",
        "stack_info", "__file__", "__spec__", "__cached__", "get_data",
    }
)  # fmt: skip

# Modules whose output depends on the calling line (warning de-duplication, log records),
# matched only when imported, so that a variable called ``warnings`` does not count.
_LAYOUT_MODULES: Final = frozenset({"warnings", "logging"})

# Builtins that run or import code built at run time; matched only as bare names, so that
# ``re.compile`` or ``store.exec`` do not count.
_DYNAMIC_BUILTINS: Final = frozenset({"eval", "exec", "compile", "__import__", "breakpoint"})

# Fragments that mark a string as a log format or a dynamic introspection key.
_LAYOUT_FRAGMENTS: Final = ("lineno", "funcName", "__code__", "__file__", "_getframe", "f_back")

# Names that can read docstrings at run time: such a file keeps its docstrings in the digest.
_DOCSTRING_READERS: Final = frozenset(
    {
        "__doc__", "getdoc", "pydoc", "doctest", "help", "typer", "click", "pydantic", "fastapi",
        "vars", "__dict__", "globals", "co_consts",
    }
)  # fmt: skip
_DOCSTRING_FRAGMENTS: Final = ("__doc__",)

# A getattr-family call whose attribute name is not a string literal could read ``__doc__``.
_DYNAMIC_ATTRIBUTE_CALLS: Final = frozenset({"getattr", "hasattr"})

_DOCSTRING_OWNERS: Final = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class StructuralDigestError(ValueError):
    """The structural digest cannot be computed here; the caller must not treat code as bound."""


class _Unclassifiable(Exception):
    """This file holds something the encoder does not know; bind it by bytes instead."""


def _require_supported_python() -> None:
    if tuple(sys.version_info[:2]) != SUPPORTED_PYTHON:
        raise StructuralDigestError(
            f"{SCHEME} is defined only for Python "
            f"{SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]}; refusing to bind code on "
            f"{sys.version_info[0]}.{sys.version_info[1]}"
        )


def _is_docstring(body: object) -> bool:
    if not isinstance(body, list) or not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and type(first.value.value) is str
    )


def _constant(value: object) -> list[object]:
    kind = type(value)
    if value is None:
        return ["None"]
    if value is Ellipsis:
        return ["Ellipsis"]
    if kind is bool:
        return ["bool", bool(value)]
    if kind is int or kind is float or kind is complex:
        return [kind.__name__, repr(value)]
    if kind is str:
        return ["str", value]
    if kind is bytes:
        assert isinstance(value, bytes)
        return ["bytes", value.hex()]
    raise _Unclassifiable(f"constant of type {kind.__name__}")


def _encode(value: object, *, strip_docstrings: bool) -> object:
    if isinstance(value, ast.AST):
        name = type(value).__name__
        if name not in _KNOWN_NODES:
            raise _Unclassifiable(f"syntax node {name}")
        fields: list[object] = []
        for field in type(value)._fields:
            if not hasattr(value, field):
                raise _Unclassifiable(f"{name} without field {field}")
            item = getattr(value, field)
            if name == "Constant" and field == "value":
                fields.append([field, _constant(item)])
                continue
            if (
                strip_docstrings
                and field == "body"
                and isinstance(value, _DOCSTRING_OWNERS)
                and _is_docstring(item)
            ):
                assert isinstance(item, list)
                item = item[1:]
            fields.append([field, _encode(item, strip_docstrings=strip_docstrings)])
        return [name, fields]
    if isinstance(value, list):
        return ["list", [_encode(item, strip_docstrings=strip_docstrings) for item in value]]
    if value is None:
        return ["None"]
    kind = type(value)
    if kind is str:
        return ["str", value]
    if kind is bool:  # MatchSingleton holds True/False directly
        return ["bool", value]
    if kind is int:
        return ["int", repr(value)]
    raise _Unclassifiable(f"field value of type {kind.__name__}")


def _referenced_names(tree: ast.AST) -> set[str]:
    """Every identifier and string constant in the file, plus markers for dynamic access."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
            if node.id in _DYNAMIC_BUILTINS:
                names.add("<dynamic-code>")
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.update(node.name.split("."))
            if node.asname:
                names.add(node.asname)
            if node.name.split(".")[0] in _LAYOUT_MODULES:
                names.add("<layout-module>")
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(node.module.split("."))
            if node.module.split(".")[0] in _LAYOUT_MODULES:
                names.add("<layout-module>")
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            names.update(node.names)
        elif isinstance(node, ast.ExceptHandler | ast.MatchAs | ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, ast.Constant) and type(node.value) is str:
            names.add(node.value)
            if any(fragment in node.value for fragment in _LAYOUT_FRAGMENTS):
                names.add("<layout-string>")
            if any(fragment in node.value for fragment in _DOCSTRING_FRAGMENTS):
                names.add("<docstring-string>")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DYNAMIC_ATTRIBUTE_CALLS
            and (
                len(node.args) < 2
                or not isinstance(node.args[1], ast.Constant)
                or type(node.args[1].value) is not str
            )
        ):
            names.add("<dynamic-attribute>")
    return names


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_binding(source: bytes) -> tuple[Mode, str]:
    """The (mode, digest) that binds one Python file's source bytes under scheme 2."""
    _require_supported_python()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(source, mode="exec", type_comments=False)
        names = _referenced_names(tree)
        if names & (_LAYOUT_READERS | {"<dynamic-code>", "<layout-string>", "<layout-module>"}):
            return "bytes", _sha256(source)
        if "<dynamic-attribute>" in names and names & {"sys", "builtins"}:
            return "bytes", _sha256(source)  # a computed lookup on the interpreter itself
        docstring_readers = _DOCSTRING_READERS | {"<docstring-string>", "<dynamic-attribute>"}
        mode: Mode = "structure-with-docstrings" if names & docstring_readers else "structure"
        encoded = _encode(tree, strip_docstrings=mode == "structure")
        canonical = json.dumps(encoded, ensure_ascii=True, separators=(",", ":"))
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError, _Unclassifiable):
        return "bytes", _sha256(source)
    return mode, _sha256(f"{SCHEME}\0{mode}\0".encode("ascii") + canonical.encode("ascii"))


def file_binding(path: Path) -> dict[str, str]:
    """One file's scheme-2 entry: structure for Python source, exact bytes for anything else."""
    try:
        # Like the byte digest, the content is bound; callers that forbid links check first.
        if not path.is_file():
            raise StructuralDigestError(f"cannot bind {path}: not a regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise StructuralDigestError(f"cannot read {path} for its approval binding") from exc
    if path.suffix != ".py":
        return {"mode": "bytes", "sha256": _sha256(raw)}
    mode, digest = source_binding(raw)
    return {"mode": mode, "sha256": digest}


def _own_bytes_sha256() -> str:
    try:
        return _sha256(Path(__file__).read_bytes())
    except OSError as exc:
        raise StructuralDigestError("cannot read the structural digest rules") from exc


def binding_digest(files: Mapping[str, Path]) -> str:
    """The scheme-2 digest of a labelled set of files (label: a stable, install-free name)."""
    _require_supported_python()
    if not files:
        raise StructuralDigestError("cannot bind an empty implementation")
    document = {
        "scheme": SCHEME,
        "python": f"{SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]}",
        "rules_sha256": _own_bytes_sha256(),
        "files": {label: file_binding(path) for label, path in sorted(files.items())},
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha256(encoded.encode("ascii"))
