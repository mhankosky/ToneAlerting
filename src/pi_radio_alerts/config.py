from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ToneSpec:
    frequency_hz: float
    duration_ms: int


@dataclass(frozen=True)
class ToneSequence:
    name: str
    tones: tuple[ToneSpec, ...]


def load_sequences(config_path: str | Path) -> list[ToneSequence]:
    raw = json.loads(Path(config_path).read_text())
    sequences: list[ToneSequence] = []
    for item in raw:
        sequences.append(
            ToneSequence(
                name=item["name"],
                tones=tuple(
                    ToneSpec(
                        frequency_hz=float(tone["frequency_hz"]),
                        duration_ms=int(tone["duration_ms"]),
                    )
                    for tone in item["tones"]
                ),
            )
        )
    return sequences

