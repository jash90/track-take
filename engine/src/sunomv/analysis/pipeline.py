"""analyze(): song + lyrics -> Analysis, with per-step wall-clock timings."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..lyrics import parse_lyrics
from ..models import Analysis, LyricLine
from . import audio_io, beats, features, sections, stems

MIX_SR = 44100


@dataclass
class Options:
    fps: float = 24.0
    language: str = "en"
    whisper_model: str = "large-v3"
    align_backend: str | None = None  # "mlx" | "torch"; None = best available
    beat_method: str = "beat_this"  # or "librosa"
    snap_distance: float = 0.6


@dataclass
class Timings:
    steps: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.steps[name] = time.perf_counter() - t0


def analyze(
    song: Path, lyrics_text: str, work_dir: Path, opts: Options | None = None
) -> tuple[Analysis, Timings]:
    opts = opts or Options()
    tm = Timings()
    methods: dict[str, str] = {}

    with tm.step("decode"):
        sha = audio_io.sha256_of(song)
        cache = audio_io.cache_dir(work_dir, sha)
        mix = audio_io.decode(song, MIX_SR, 2)
        duration = len(mix) / MIX_SR
        blocks = parse_lyrics(lyrics_text)

    with tm.step("stems"):
        paths, dev = stems.separate(mix, MIX_SR, cache / "stems")
        methods["stems"] = f"demucs htdemucs ({dev})"
    del mix

    with tm.step("beats"):
        mix_22k = audio_io.to_mono(audio_io.decode(song, features.SR, 1))
        grid = beats.track(mix_22k, features.SR, prefer=opts.beat_method)
        methods["beats"] = grid.method

    with tm.step("align"):
        from .align import align_lines

        flat = [(bi, ln) for bi, b in enumerate(blocks) for ln in b.lines]
        block_lines: list[list[LyricLine]] = [[] for _ in blocks]
        if flat:
            vocals_16k = audio_io.to_mono(audio_io.decode(paths["vocals"], 16000, 1))
            aligned, methods["alignment"] = align_lines(
                vocals_16k, [ln for _, ln in flat], opts.language, opts.whisper_model, opts.align_backend
            )
            for (bi, _), line in zip(flat, aligned):
                block_lines[bi].append(line)
        lines = [ln for bl in block_lines for ln in bl]

    with tm.step("sections"):
        secs = sections.build_sections(blocks, block_lines, duration, grid.downbeats, opts.snap_distance)
        methods["sections"] = f"lyric tags + aligned words, snapped to downbeats within {opts.snap_distance}s"

    with tm.step("features"):
        stem_feats = {"mix": features.stem_features(mix_22k, duration, opts.fps)}
        hits: dict = {}
        for name, p in paths.items():
            y = audio_io.to_mono(audio_io.decode(p, features.SR, 1))
            stem_feats[name] = features.stem_features(y, duration, opts.fps)
            if name == "drums":
                hits = features.drum_hits(y)
        methods["drum_hits"] = "band-split spectral flux on drums stem (kick 30-150, snare 1k-5k, hat 7k+ Hz)"

    analysis = Analysis(
        audio_sha256=sha,
        duration=round(duration, 4),
        sample_rate=MIX_SR,
        bpm=grid.bpm,
        beats=grid.beats,
        downbeats=grid.downbeats,
        beats_per_bar=grid.beats_per_bar,
        sections=secs,
        lines=lines,
        stems=stem_feats,
        drum_hits=hits,
        language=opts.language,
        methods=methods,
    )
    return analysis, tm
