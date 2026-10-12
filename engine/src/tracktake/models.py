"""Data contracts shared by analysis, planning and rendering.

All times are stored in seconds. They are quantised to frames only at render time (see timegrid.py).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Word(BaseModel):
    text: str
    start: float
    end: float


class LyricLine(BaseModel):
    text: str
    start: float
    end: float
    words: list[Word] = Field(default_factory=list)


class Section(BaseModel):
    """A song part. Labels come from Suno lyric tags, e.g. "Verse 1", "Chorus", "Instrumental Break"."""

    label: str
    kind: str  # normalised: intro|verse|pre_chorus|chorus|build|break|bridge|breakdown|outro|other
    start: float
    end: float
    tag_details: str = ""  # text after the colon in the Suno tag, e.g. "Full Band, Powerful and Emotional"
    lines: list[LyricLine] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)  # non-structural Suno tags in this part, e.g. "Rain"


class Onset(BaseModel):
    time: float
    strength: float  # normalised 0..1 within its stream


class Envelope(BaseModel):
    """A feature sampled once per video frame at `fps`, normalised to 0..1."""

    fps: float
    values: list[float]


class StemFeatures(BaseModel):
    onsets: list[Onset] = Field(default_factory=list)
    envelopes: dict[str, Envelope] = Field(default_factory=dict)  # e.g. "rms", "low", "mid", "high"


class Analysis(BaseModel):
    version: int = 1
    audio_sha256: str
    duration: float
    sample_rate: int
    bpm: float
    beats: list[float]
    downbeats: list[float]
    beats_per_bar: int = 4
    sections: list[Section] = Field(default_factory=list)
    lines: list[LyricLine] = Field(default_factory=list)
    stems: dict[str, StemFeatures] = Field(default_factory=dict)  # "mix", "vocals", "drums", "bass", "other"
    drum_hits: dict[str, list[Onset]] = Field(default_factory=dict)  # "kick", "snare", "hat"
    language: str = ""  # lyrics language used for alignment, e.g. "en", "pl"
    methods: dict[str, str] = Field(default_factory=dict)  # step -> algorithm/model used, e.g. "beats"
