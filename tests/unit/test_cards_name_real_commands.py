"""Every card and skill the product ships names only ``alpha`` commands that exist.

The list of real commands, sub-commands and options comes from the program itself
(``alpha info commands --all --json``). Cards also say ``alpha ...``, not ``uv run alpha ...``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).parents[2]
CARDS = sorted((ROOT / "research/tools").glob("*.md"))
SKILLS = sorted((ROOT / ".claude/skills").glob("*/SKILL.md")) + sorted(
    (ROOT / ".agents/skills").glob("*/SKILL.md")
)
NEW_CARDS = ("lookalike.md", "forecast.md", "data.md", "setup-spec.md")
CARD_MAX_LINES = 40
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_SPAN = re.compile(r"`([^`\n]+)`")
_CALL = re.compile(r"(?:^|(?<=[\s$(]))(?:uv run )?alpha(?= |$)")
_SPLIT = re.compile(r"\||&&|;|(?:uv run )?\balpha\b")
_PLACEHOLDER = re.compile(r"<[^<>]*>|\.\.\.")
_WORD = re.compile(r"[a-z][a-z-]*$")


@cache
def _catalog() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    out = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "info", "commands", "--all", "--json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    leaves: dict[str, frozenset[str]] = {
        entry["id"]: frozenset(o["flag"] for o in entry["options"] if o["flag"])
        for entry in json.loads(out)
    }
    groups = {
        " ".join(parts[:n])
        for leaf in leaves
        for parts in [leaf.split()]
        for n in range(1, len(parts))
    }
    return frozenset(leaves) | frozenset(groups), {k: v for k, v in leaves.items()}


def _segments(path: Path) -> list[str]:
    """Inline code spans and fenced lines of a document, after its front matter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        lines = lines[lines.index("---", 1) + 1 :]
    found: list[str] = []
    inside = False
    for line in lines:
        if _FENCE.match(line):
            inside = not inside
        elif inside:
            found.append(line.strip())
        else:
            found += [s.strip() for s in _SPAN.findall(line)]
    return found


def _calls(segment: str) -> list[str]:
    """The text after each ``alpha`` in a segment, up to the next pipe, ``&&`` or ``alpha``."""
    calls: list[str] = []
    for match in _CALL.finditer(segment):
        tail = segment[match.end() :]
        calls.append(_SPLIT.split(tail, maxsplit=1)[0].strip())
    return calls


def problems(path: Path) -> list[str]:
    known, leaves = _catalog()
    found: list[str] = []
    for segment in _segments(path):
        for call in _calls(segment):
            words: list[str] = []
            options: list[str] = []
            done = False  # the first argument value ends the command words
            for token in _PLACEHOLDER.sub("<x>", call).split():
                if token.startswith("--"):
                    options.append(token.partition("=")[0])
                elif done or token.startswith(("-", "<")) or options:
                    continue
                elif _WORD.match(token) and " ".join([*words, token]) in known:
                    words.append(token)
                elif words and " ".join(words) in leaves:
                    done = True  # an argument value
                else:
                    found.append(f"{path.name}: no command 'alpha {' '.join([*words, token])}'")
                    done = True
            leaf = " ".join(words)
            if leaf in leaves:
                bad = [o for o in options if o not in leaves[leaf] and o != "--help"]
                found += [f"{path.name}: 'alpha {leaf}' has no option {o}" for o in bad]
    return found


def test_cards_name_only_real_commands() -> None:
    wrong = [p for card in CARDS for p in problems(card)]
    assert wrong == []


def test_skills_name_only_real_commands() -> None:
    wrong = [p for skill in SKILLS for p in problems(skill)]
    assert wrong == []


def test_cards_say_alpha_not_uv_run_alpha_except_once_in_the_index() -> None:
    for card in CARDS:
        text = card.read_text(encoding="utf-8")
        if card.name == "README.md":
            assert text.count("uv run alpha") == 1, "say once how to run from a checkout"
        else:
            assert "uv run alpha" not in text, card.name


def test_no_card_or_skill_mentions_touch_id() -> None:
    for path in [*CARDS, *SKILLS]:
        assert "touch id" not in path.read_text(encoding="utf-8").lower(), path.name


def test_new_cards_exist_are_short_and_are_indexed() -> None:
    index = (ROOT / "research/tools/README.md").read_text(encoding="utf-8")
    for name in NEW_CARDS:
        card = ROOT / "research/tools" / name
        assert card.is_file(), name
        assert len(card.read_text(encoding="utf-8").splitlines()) <= CARD_MAX_LINES, name
        assert f"({name})" in index, name


def test_owner_auth_command_group_is_gone() -> None:
    help_text = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "--help"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "owner-auth" not in help_text
    assert "Touch ID" not in help_text
    called = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "owner-auth", "--help"],
        capture_output=True,
        text=True,
    )
    assert called.returncode != 0
    assert "enroll" not in called.stdout


def test_example_setup_spec_loads_and_has_every_section() -> None:
    from alpha_cli.spine.setup_find import load_setup_spec

    path = ROOT / "research/examples/setup-spec.example.toml"
    spec = load_setup_spec(path)
    assert spec.exit is not None
    assert spec.study is not None
    assert spec.trigger is not None
    assert dict(spec.reference)
    assert dict(spec.filters)
    card = (ROOT / "research/tools/setup-spec.md").read_text(encoding="utf-8")
    for section in (
        "[setup]",
        "[filters]",
        "[trigger]",
        "[reference]",
        "[context]",
        "[exit]",
        "[study]",
    ):
        assert section in card, section


def test_unknown_root_command_and_option_are_reported(tmp_path: Path) -> None:
    card = tmp_path / "x.md"
    card.write_text("`alpha nosuchcommand --invalid`\n`alpha test --bogus`\n", encoding="utf-8")
    found = problems(card)
    assert any("nosuchcommand" in line for line in found)
    assert any("--bogus" in line for line in found)
