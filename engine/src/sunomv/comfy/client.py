"""Minimal ComfyUI HTTP + WebSocket client: upload inputs, queue an API-format graph, wait, fetch outputs."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from websockets.sync.client import connect


class ComfyError(RuntimeError):
    pass


@dataclass
class Result:
    prompt_id: str
    seconds: float
    images: list[bytes] = field(default_factory=list)


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 3600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex
        self.http = httpx.Client(base_url=self.base_url, timeout=60.0)

    def object_info(self) -> dict:
        return self.http.get("/object_info").raise_for_status().json()

    def upload_image(self, path: str | Path, name: str | None = None) -> str:
        """Upload into ComfyUI's input folder and return the name to use in LoadImage."""
        path = Path(path)
        with path.open("rb") as f:
            r = self.http.post(
                "/upload/image",
                files={"image": (name or path.name, f)},
                data={"type": "input", "overwrite": "true"},
            )
        info = r.raise_for_status().json()
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    def run(self, graph: dict) -> Result:
        """Queue `graph`, block until it finishes, and return every image saved by its output nodes."""
        ws_url = self.base_url.replace("http", "ws", 1) + f"/ws?clientId={self.client_id}"
        started = time.monotonic()
        with connect(ws_url, max_size=None, open_timeout=30) as ws:
            r = self.http.post("/prompt", json={"prompt": graph, "client_id": self.client_id})
            if r.status_code != 200:
                raise ComfyError(f"/prompt rejected the graph: {r.text[:2000]}")
            prompt_id = r.json()["prompt_id"]
            while True:
                remaining = self.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise ComfyError(f"timed out after {self.timeout:.0f}s waiting for {prompt_id}")
                raw = ws.recv(timeout=remaining)
                if isinstance(raw, bytes):
                    continue  # binary latent previews
                msg = json.loads(raw)
                data = msg.get("data", {})
                if data.get("prompt_id") != prompt_id:
                    continue
                if msg["type"] == "execution_error":
                    raise ComfyError(f"{data.get('node_type')}: {data.get('exception_message')}")
                if msg["type"] == "execution_success":
                    break
        seconds = time.monotonic() - started
        return Result(prompt_id, seconds, self._images(prompt_id))

    def _images(self, prompt_id: str) -> list[bytes]:
        history = self.http.get(f"/history/{prompt_id}").raise_for_status().json()[prompt_id]
        images = []
        for output in history["outputs"].values():
            for img in output.get("images", []):
                if img.get("type") != "output":
                    continue
                params = {"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]}
                images.append(self.http.get("/view", params=params).raise_for_status().content)
        return images
