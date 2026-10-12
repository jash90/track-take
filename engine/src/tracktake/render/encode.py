"""Stream RGB frames into FFmpeg and mux the song audio (no intermediate PNGs on disk)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Self

import numpy as np

from tracktake.render.encoders import video_args


class VideoWriter:
    def __init__(
        self,
        path: str | Path,
        width: int,
        height: int,
        fps: float,
        audio: str | Path | None = None,
        audio_start: float = 0.0,
        duration: float | None = None,
        bitrate: str = "14M",
    ):
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
        if audio:
            cmd += ["-ss", f"{audio_start:.3f}"]
            if duration is not None:
                cmd += ["-t", f"{duration:.3f}"]
            cmd += ["-i", str(audio)]
        # hardware H.264 (VideoToolbox on a Mac, NVENC on Vast) keeps the CPU free for compositing
        cmd += video_args("h264", bitrate)
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
        cmd += ["-movflags", "+faststart", str(path)]
        self.size = (height, width, 3)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray, repeat: int = 1) -> None:
        if frame.shape != self.size:
            raise ValueError(f"frame {frame.shape} != {self.size}")
        data = np.ascontiguousarray(frame).tobytes()
        for _ in range(repeat):
            self.proc.stdin.write(data)

    def close(self) -> None:
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg exited with {self.proc.returncode}")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
