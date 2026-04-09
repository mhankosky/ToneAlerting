from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic

from .config import ToneSequence, ToneSpec


@dataclass(frozen=True)
class ToneSegment:
    frequency_hz: float
    duration_ms: int
    ended_at: float


@dataclass(frozen=True)
class MatchResult:
    sequence: ToneSequence
    matched_at: float


class SequenceMatcher:
    def __init__(
        self,
        sequences: list[ToneSequence],
        *,
        frequency_tolerance_hz: float = 18.0,
        match_cooldown_s: float = 10.0,
    ) -> None:
        self._sequences = sorted(sequences, key=lambda seq: len(seq.tones))
        self._frequency_tolerance_hz = frequency_tolerance_hz
        self._match_cooldown_s = match_cooldown_s
        self._recent_segments: deque[ToneSegment] = deque(maxlen=8)
        self._last_match_times: dict[str, float] = {}

    def add_segment(self, segment: ToneSegment) -> MatchResult | None:
        self._recent_segments.append(segment)
        now = segment.ended_at
        matched: MatchResult | None = None

        for sequence in self._sequences:
            needed = len(sequence.tones)
            if len(self._recent_segments) < needed:
                continue
            candidate = list(self._recent_segments)[-needed:]
            if self._matches(sequence.tones, candidate):
                last_time = self._last_match_times.get(sequence.name)
                if last_time is None or now - last_time >= self._match_cooldown_s:
                    self._last_match_times[sequence.name] = now
                    matched = MatchResult(sequence=sequence, matched_at=now)
        return matched

    def _matches(
        self,
        tones: tuple[ToneSpec, ...],
        segments: list[ToneSegment],
    ) -> bool:
        for tone, segment in zip(tones, segments):
            if abs(tone.frequency_hz - segment.frequency_hz) > self._frequency_tolerance_hz:
                return False

            min_duration = max(600, int(tone.duration_ms * 0.65))
            max_duration = int(tone.duration_ms * 1.6) + 400
            if not (min_duration <= segment.duration_ms <= max_duration):
                return False
        return True

    def inject_match(self, name: str) -> MatchResult:
        sequence = next(sequence for sequence in self._sequences if sequence.name == name)
        now = monotonic()
        self._last_match_times[name] = now
        return MatchResult(sequence=sequence, matched_at=now)
