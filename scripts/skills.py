#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["questionary>=2.0", "prompt_toolkit>=3.0"]
# ///
"""Pick which skills get symlinked into skills/.

    uv run scripts/skills.py [--dry-run]

skills/ is a flat directory of symlinks, and is what every CLI's skill directory points
at. It is gitignored, so this just edits it in place — there is nothing to commit.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import questionary
from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, ScrollOffsets, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth

# Where each source keeps its skills. Hardcoded because a blind search would also turn up
# translated copies (docs/ja-JP/skills, .cursor/, ...) inside some submodules.
SOURCE_ROOTS = {
    "everything-claude-code": "everything-claude-code/skills",
    "book-to-skill": "book-to-skill",
    "superpowers": "superpowers/skills",
    "caveman": "caveman/skills",
    "andrej-karpathy-skills": "andrej-karpathy-skills/skills",
    "academic-research-skills": "academic-research-skills",
    "mattpocock-skills": "mattpocock-skills/skills",
    "context-engineering-kit": "context-engineering-kit/plugins",
    "personal-skills": "personal-skills",
    "ponytail": "ponytail/skills",
    "i-have-adhd": "i-have-adhd/skills/i-have-adhd",
}

NESTED_SOURCES = {"book-to-skill", "mattpocock-skills", "context-engineering-kit", "i-have-adhd"}

HELP = (
    "↑↓ move · ←→ pan · space toggle · tab fold (shift-tab: all)"
    " · type to filter · enter apply · ctrl-c cancel"
)
GREEN, RED, OFF = "\033[32m", "\033[31m", "\033[0m"


def describe(skill_md: Path) -> str:
    """Pull `description` out of the frontmatter, up to the next top-level key.

    Hand-rolled rather than YAML: descriptions routinely contain unquoted colons
    ("Triggers on: review paper"), which a real YAML parser rejects.
    """
    text = skill_md.read_text("utf-8-sig", errors="replace")  # -sig tolerates a BOM
    block = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not block:
        return ""
    desc = re.search(r"^description:(.*?)(?=^\S+:|\Z)", block.group(1) + "\n", re.M | re.S)
    return " ".join(desc.group(1).split()) if desc else ""


def source_of(target: str) -> str | None:
    """Which source a symlink points into, or None if it points somewhere we don't know."""
    for source, rel in SOURCE_ROOTS.items():
        if target.startswith(f"../{rel}/"):
            return source
    return None


def checked_out(root: Path) -> set[str]:
    """The sources actually present on disk.

    An empty directory means the source is NOT checked out: `git clone` without
    --recursive leaves the submodule path behind as one. `.git` alone doesn't count as
    content either — an interrupted `submodule update` writes it before the worktree, and
    `rm -rf <sub>/*` leaves it behind because globs skip dotfiles. A source that is
    checked out but currently offers no skills is still present, and its stale links are
    still ours to clean up.
    """
    return {
        source
        for source, rel in SOURCE_ROOTS.items()
        if (root / rel).is_dir() and any(p.name != ".git" for p in (root / rel).iterdir())
    }


def occupied(path: Path) -> bool:
    """Something that isn't one of our symlinks is sitting there."""
    return path.exists() and not path.is_symlink()


@dataclass(frozen=True)
class Skill:
    source: str
    name: str
    path: str
    description: str

    @property
    def target(self) -> str:
        """Symlink target, relative to skills/."""
        return f"../{SOURCE_ROOTS[self.source]}/{self.path}"

    def is_linked(self, current: dict[str, str]) -> bool:
        return current.get(self.name) == self.target

    @classmethod
    def scan(cls, root: Path, sources: set[str]) -> list[Skill]:
        """Every skill on offer, using recursive scanning for nested sources."""
        scanned: list[Skill] = []
        for source, rel in SOURCE_ROOTS.items():
            if source not in sources:
                continue
            source_root = root / rel
            if source in NESTED_SOURCES:
                skill_files = sorted(source_root.rglob("SKILL.md"))
            else:
                skill_files = sorted(
                    skill_md
                    for skill_md in source_root.glob("*/SKILL.md")
                    if skill_md.is_file()
                )
            scanned.extend(
                cls(
                    source,
                    skill_md.parent.name,
                    skill_md.parent.relative_to(source_root).as_posix(),
                    describe(skill_md),
                )
                for skill_md in skill_files
            )
        return scanned

    @staticmethod
    def linked(skills_dir: Path) -> dict[str, str]:
        """Link name -> target, for the symlinks in skills/ right now."""
        return {e.name: os.readlink(e) for e in sorted(skills_dir.iterdir()) if e.is_symlink()}


class Picker:
    """One list holding both sources and their skills.

    Toggling a source row toggles every skill under it, so a whole repo goes in or out in
    one keystroke. questionary's checkbox is flat and can't cascade like that, hence the
    hand-rolled prompt_toolkit app.
    """

    PAN_STEP = 8

    def __init__(self, skills: list[Skill], current: dict[str, str]) -> None:
        self.skills = skills
        self.chosen = {s for s in skills if s.is_linked(current)}
        self.collapsed: set[str] = set()
        self.filter = ""
        self.cursor = 0
        self.offset = 0  # descriptions run long, so rows pan sideways as a whole
        self.ceiling = 0  # how far the pan may go; render() derives it from the rows on screen
        self.pad = max(len(s.name) for s in skills) + 2
        # Precomputed: rows() re-filters every skill on every frame.
        self.haystack = {s: f"{s.source} {s.name} {s.description}".lower() for s in skills}
        self.render()  # primes `ceiling`, so pan() works even if a key beats the first draw

    @property
    def width(self) -> int:
        """Read per render, so resizing the terminal takes effect."""
        return max(shutil.get_terminal_size().columns - 3, 1)

    def is_folded(self, source: str) -> bool:
        # A filter overrides folding, so searching always surfaces its matches.
        return source in self.collapsed and not self.filter

    def rows(self) -> list[tuple[Skill | None, list[Skill]]]:
        """Visible rows. A source row is (None, group); a skill row is (skill, group)."""
        rows: list[tuple[Skill | None, list[Skill]]] = []
        for source in SOURCE_ROOTS:
            group = [
                s for s in self.skills if s.source == source and self.filter in self.haystack[s]
            ]
            if not group:
                continue
            rows.append((None, group))
            if not self.is_folded(source):
                rows.extend((s, group) for s in group)
        return rows

    def move(self, delta: int) -> None:
        self.cursor = min(max(self.cursor + delta, 0), max(len(self.rows()) - 1, 0))

    def pan(self, delta: int) -> None:
        self.offset = min(max(self.offset + delta, 0), self.ceiling)

    def refilter(self, text: str) -> None:
        self.filter, self.cursor, self.offset = text, 0, 0

    def backspace(self) -> None:
        if self.filter:
            self.refilter(self.filter[:-1])

    def fold(self, shut: bool) -> None:
        """Fold a source away, or unfold it. From a skill row, acts on its source."""
        rows = self.rows()
        if self.filter or not rows:  # a filter already overrides folding — don't set it unseen
            return
        source = rows[self.cursor][1][0].source
        self.offset = 0  # the view just changed wholesale; don't strand the pan
        if not shut:
            self.collapsed.discard(source)
            return
        self.collapsed.add(source)
        # Park the cursor on the source row we just folded, since its skills are gone.
        self.cursor = next(i for i, (_, g) in enumerate(self.rows()) if g[0].source == source)

    def fold_toggle(self) -> None:
        rows = self.rows()
        if rows and not self.filter:
            self.fold(rows[self.cursor][1][0].source not in self.collapsed)

    def fold_all(self) -> None:
        if self.filter:
            return
        sources = {s.source for s in self.skills}
        self.collapsed = set() if self.collapsed >= sources else sources
        self.cursor = self.offset = 0

    def toggle(self) -> None:
        rows = self.rows()
        if not rows:
            return
        skill, group = rows[self.cursor]
        if skill is not None:
            self.chosen ^= {skill}
            return
        # A source row covers whatever the filter shows, which with no filter is the whole
        # repo — matching the (n/len) count on the row itself.
        covered = set(group)
        if covered <= self.chosen:
            self.chosen -= covered
        else:
            self.chosen |= covered

    def window(self, text: str, width: int) -> str:
        """The slice of a row visible at the current pan offset.

        Walked a cell at a time, not a character at a time: CJK descriptions are
        double-width and would otherwise overflow the right edge. A leading … marks text
        panned off the left, a trailing … marks text running off the right.
        """
        lead = "…" if self.offset else ""
        budget = width - get_cwidth(lead)
        if budget <= 0:  # a terminal too narrow for even one column of text
            return "…"[:width]

        shown, used, skipped = [], 0, 0
        for char in text:
            cells = get_cwidth(char)
            if skipped < self.offset:  # still scrolled off to the left
                skipped += cells
                continue
            if not shown and skipped > self.offset:  # a double-width char straddled the edge
                shown.append(" ")
                used += 1
            if used + cells > budget:
                while shown and used + 1 > budget:  # give back a cell for the trailing …
                    used -= get_cwidth(shown.pop())
                return f"{lead}{''.join(shown)}…"
            shown.append(char)
            used += cells
        return f"{lead}{''.join(shown)}"

    def line(self, skill: Skill | None, group: list[Skill]) -> tuple[str, str]:
        """A row's full text and style, before panning."""
        if skill is None:
            n = sum(s in self.chosen for s in group)
            box = "x" if n == len(group) else "~" if n else " "
            arrow = "▸" if self.is_folded(group[0].source) else "▾"
            return f"{arrow} [{box}] {group[0].source}  ({n}/{len(group)})", "class:source"
        box = "x" if skill in self.chosen else " "
        return f"    [{box}] {skill.name:<{self.pad}}{skill.description or '—'}", ""

    def render(self) -> list[tuple[str, str]]:
        """Draw the rows and, since it is already walking them, set the pan ceiling.

        pan() and head() then clamp against that in O(1). Only a resize can move the
        ceiling without a keystroke, and this catches that on the very next frame.
        """
        width = self.width  # hoisted: the property does an ioctl, and this runs per row
        rows = self.rows()
        if not rows:
            self.offset = self.ceiling = 0
            return [("class:dim", self.window(f"  nothing matches {self.filter!r}", width) + "\n")]

        lines = [self.line(skill, group) for skill, group in rows]
        self.ceiling = max(max(get_cwidth(text) for text, _ in lines) - width + 1, 0)
        self.offset = min(self.offset, self.ceiling)

        out = []
        for i, (text, style) in enumerate(lines):
            here = i == self.cursor
            row = f"{'❯' if here else ' '} {self.window(text, width)}\n"
            out.append(("class:cursor" if here else style, row))
        return out

    def head(self) -> str:
        self.offset = min(self.offset, self.ceiling)  # O(1): render() keeps the ceiling current
        chosen = f"{len(self.chosen)}/{len(self.skills)} selected"
        panned = f" · panned +{self.offset}" if self.offset else ""
        return f" {chosen} · filter: {self.filter or '—'}{panned}\n {HELP}\n"

    def run(self) -> list[Skill] | None:
        """Returns the chosen skills, or None if the user cancelled."""
        kb = KeyBindings()
        kb.add("up")(lambda _: self.move(-1))
        kb.add("down")(lambda _: self.move(1))
        kb.add("pageup")(lambda _: self.move(-10))
        kb.add("pagedown")(lambda _: self.move(10))
        kb.add("left")(lambda _: self.pan(-self.PAN_STEP))
        kb.add("right")(lambda _: self.pan(self.PAN_STEP))
        kb.add("home")(lambda _: self.pan(-self.offset))
        kb.add("space")(lambda _: self.toggle())
        kb.add("tab")(lambda _: self.fold_toggle())
        kb.add("s-tab")(lambda _: self.fold_all())
        kb.add("backspace")(lambda _: self.backspace())
        kb.add("c-c")(lambda e: e.app.exit(result=None))
        kb.add("enter")(
            lambda e: e.app.exit(result=sorted(self.chosen, key=lambda s: (s.source, s.name)))
        )

        @kb.add("<any>")
        def _(event) -> None:
            if event.data.isprintable():
                self.refilter(self.filter + event.data.lower())

        body = Window(
            FormattedTextControl(self.render, get_cursor_position=lambda: Point(0, self.cursor)),
            scroll_offsets=ScrollOffsets(top=2, bottom=2),
        )
        layout = Layout(HSplit([Window(FormattedTextControl(self.head), height=2), body]))
        style = Style.from_dict({"source": "bold cyan", "cursor": "reverse", "dim": "italic"})
        return Application(layout=layout, key_bindings=kb, style=style, full_screen=True).run()


def resolve_conflicts(selected: list[Skill]) -> list[Skill] | None:
    """Settle skills that several sources offer under the same name.

    skills/ is one flat namespace, so only one of them can be linked. Returns None if the
    user cancels.
    """
    by_name: dict[str, list[Skill]] = {}
    for skill in selected:
        by_name.setdefault(skill.name, []).append(skill)

    kept = []
    for name, claimants in by_name.items():
        if len(claimants) == 1:
            kept.append(claimants[0])
            continue

        winner = questionary.select(
            f"'{name}' is offered by several sources — keep which?",
            choices=[questionary.Choice(skill.source, skill) for skill in claimants],
        ).ask()
        if winner is None:  # ctrl-c
            return None
        kept.append(winner)

    return kept


def relink(skills_dir: Path, add: list[Skill], remove: list[str]) -> None:
    for name in remove:
        link = skills_dir / name
        if link.is_symlink():  # never delete anything we didn't create
            link.unlink()
    for skill in add:
        link = skills_dir / skill.name
        if link.is_symlink():  # retargeting an existing link, e.g. a resolved conflict
            link.unlink()
        link.symlink_to(skill.target)


def main() -> int:
    if unknown := [arg for arg in sys.argv[1:] if arg != "--dry-run"]:
        sys.exit(f"unknown option: {' '.join(unknown)}")  # a typo'd --dry-run must not apply
    dry_run = "--dry-run" in sys.argv[1:]

    root = Path(__file__).resolve().parent.parent
    if not (root / ".gitmodules").is_file():
        sys.exit(f"not a llm-config checkout: {root}")
    skills_dir = root / "skills"
    skills_dir.mkdir(exist_ok=True)

    sources = checked_out(root)
    available = Skill.scan(root, sources)
    if not available:
        sys.exit("no skills found — run `git submodule update --init --recursive`")

    # A source that isn't checked out scans as nothing, which would make its links look like
    # skills the user had just deselected. Freeze those, and any link we don't recognise.
    links = Skill.linked(skills_dir)
    current = {name: t for name, t in links.items() if source_of(t) in sources}
    frozen = sorted(links.keys() - current.keys())
    if frozen:
        print(f"source not checked out, leaving alone: {', '.join(frozen)}\n")

    selected = Picker(available, current).run()
    if selected is None or (selected := resolve_conflicts(selected)) is None:
        return 1

    wanted = {s.name: s for s in selected}
    add = sorted((s for s in selected if not s.is_linked(current)), key=lambda s: s.name)
    remove = sorted(name for name in current if name not in wanted)

    # A name we promised to leave alone must not be quietly retargeted: a frozen link (whose
    # real claimant we can't even see, to offer as a conflict), or something that isn't a
    # symlink at all — we never delete those, so we can't link over them either.
    blocked = [s for s in add if s.name in frozen or occupied(skills_dir / s.name)]
    if blocked:
        print(f"name already taken, skipping: {', '.join(sorted(s.name for s in blocked))}\n")
        add = [s for s in add if s not in blocked]

    if not add and not remove:
        print("Nothing to change.")
        return 0
    for skill in add:
        print(f"  {GREEN}+ {skill.name}{OFF}  ({skill.source})")
    for name in remove:
        print(f"  {RED}- {name}{OFF}")
    print()

    if dry_run:
        print("--dry-run: nothing written.")
        return 0
    if not questionary.confirm(f"Apply? (+{len(add)} / -{len(remove)})", default=True).ask():
        return 1

    relink(skills_dir, add, remove)
    # Counted off disk, not off `wanted`, which still holds the skills we had to skip.
    print(f"\nDone: {len(Skill.linked(skills_dir))} linked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
