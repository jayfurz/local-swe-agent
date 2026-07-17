"""Harness configuration: flags > environment > defaults."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_URL = "http://localhost:8009/v1"
DEFAULT_MAX_TURNS = 40
DEFAULT_TEMPERATURE = 0.1


@dataclass
class HarnessConfig:
    base_url: str
    model: str
    api_key: str = "local"
    workspace: Path = field(default_factory=Path.cwd)
    max_turns: int = DEFAULT_MAX_TURNS
    temperature: float = DEFAULT_TEMPERATURE


def detect_model(base_url: str, api_key: str = "local", timeout: float = 5.0) -> str:
    """Return the first model id the server advertises at GET {base_url}/models."""
    req = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    models = [entry["id"] for entry in data.get("data", []) if "id" in entry]
    if not models:
        raise RuntimeError(f"server at {base_url} advertises no models")
    return models[0]
