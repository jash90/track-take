"""Suno lyrics -> ordered blocks.

Structural tags ("[Verse 1: Female Vocal, Soft]", "[Build-Up]", "[Silence]") open a block; a block without
sung lines is instrumental. Any other tag ("[Rain]", "[Phone Static]", "[Female Whisper]", "[Fade Out]") is a
hint attached to the surrounding block, not a section of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TAG_RE = re.compile(r"\[([^\[\]]*)\]")

# Checked in order: the first rule whose pattern matches the tag label wins.
KIND_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("pre_chorus", re.compile(r"\bpre[-\s]?chorus\b")),
    ("chorus", re.compile(r"\bpost[-\s]?chorus\b")),
    ("intro", re.compile(r"\bintro\b")),
    ("outro", re.compile(r"\boutro\b|^end$")),
    ("breakdown", re.compile(r"\bbreak[-\s]?down\b")),
    ("bridge", re.compile(r"\bbridge\b")),
    ("build", re.compile(r"\bbuild(?:[-\s]?up)?\b|\briser\b")),
    ("chorus", re.compile(r"\bchorus\b|\bhook\b|\brefrain\b|\bdrop\b")),
    ("verse", re.compile(r"\bverse\b")),
    ("break", re.compile(r"\bbreak\b|\binstrumental\b|\binterlude\b|\bsolo\b|\bsilence\b|\bpause\b")),
]
INSTRUMENTAL_KINDS = {"break", "build"}


@dataclass
class LyricBlock:
    label: str
    kind: str
    tag_details: str = ""
    lines: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    @property
    def instrumental(self) -> bool:
        return not self.lines


def kind_of(label: str) -> str | None:
    """Normalised section kind for a tag label, or None when the tag is not structural."""
    low = label.strip().lower()
    for kind, pattern in KIND_RULES:
        if pattern.search(low):
            return kind
    return None


def split_tag(tag: str) -> tuple[str, str]:
    """'Verse 1: Female Vocal, Soft' -> ('Verse 1', 'Female Vocal, Soft')."""
    label, _, details = tag.partition(":")
    return label.strip(), details.strip()


def clean_line(line: str) -> str:
    """Drop inline bracket tags and collapse whitespace."""
    return " ".join(TAG_RE.sub(" ", line).split())


def parse_lyrics(text: str) -> list[LyricBlock]:
    """Parse Suno lyrics into ordered blocks (see module docstring)."""
    blocks: list[LyricBlock] = []
    current: LyricBlock | None = None
    raw = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(raw):
        if not line:
            continue
        tag = TAG_RE.fullmatch(line)
        if tag is None:
            sung = clean_line(line)
            if not sung:
                continue
            if current is None:
                current = LyricBlock(label="", kind="other")
                blocks.append(current)
            current.lines.append(sung)
            continue

        label, details = split_tag(tag.group(1))
        if not label:
            continue
        kind = kind_of(label)
        if kind is None and _opens_sung_block(raw, i, current):
            kind = "other"
        if kind is None:
            if current is None:  # hint before any section: hold it in a leading intro-less block
                current = LyricBlock(label="", kind="other")
                blocks.append(current)
            current.hints.append(tag.group(1).strip())
            continue
        current = LyricBlock(label=label, kind=kind, tag_details=details)
        blocks.append(current)
    return _drop_empty_untitled(blocks)


def _opens_sung_block(raw: list[str], i: int, current: LyricBlock | None) -> bool:
    """An unknown tag starts its own block only when lines follow it and there is no sung block to join."""
    nxt = next((ln for ln in raw[i + 1 :] if ln), "")
    lines_follow = bool(nxt) and TAG_RE.fullmatch(nxt) is None
    return lines_follow and (current is None or current.kind in INSTRUMENTAL_KINDS)


def _drop_empty_untitled(blocks: list[LyricBlock]) -> list[LyricBlock]:
    """A leading untitled block holding only hints merges its hints into the next block."""
    if len(blocks) > 1 and not blocks[0].label and not blocks[0].lines:
        blocks[1].hints = blocks[0].hints + blocks[1].hints
        return blocks[1:]
    return blocks


def sung_lines(blocks: list[LyricBlock]) -> list[tuple[int, str]]:
    """(block index, line text) for every sung line, in order."""
    return [(bi, ln) for bi, b in enumerate(blocks) for ln in b.lines]
