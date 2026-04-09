from __future__ import annotations

from dataclasses import dataclass
import math
from time import monotonic

import numpy as np

from .matcher import MatchResult, SequenceMatcher, ToneSegment


@dataclass
class _ActiveTone:
    frequency_hz: float
    started_at: float
    last_seen_at: float
    frames: int = 1


class QuickCallDetector:
    def __init__(
        self,
        matcher: SequenceMatcher,
        *,
        sample_rate: int = 22050,
        window_size: int = 2048,
        step_size: int = 1024,
        min_frequency_hz: float = 250.0,
        max_frequency_hz: float = 3000.0,
        min_rms: float = 350.0,
        peak_ratio_threshold: float = 0.42,
        frequency_tolerance_hz: float = 18.0,
    ) -> None:
        self.matcher = matcher
        self.sample_rate = sample_rate
        self.window_size = window_size
        self.step_size = step_size
        self.min_frequency_hz = min_frequency_hz
        self.max_frequency_hz = max_frequency_hz
        self.min_rms = min_rms
        self.peak_ratio_threshold = peak_ratio_threshold
        self.frequency_tolerance_hz = frequency_tolerance_hz
        self._buffer = np.array([], dtype=np.int16)
        self._window = np.hanning(window_size)
        self._active_tone: _ActiveTone | None = None
        self._stream_time_s = 0.0

    def feed(self, samples: np.ndarray) -> list[MatchResult]:
        if samples.size == 0:
            return []

        self._buffer = np.concatenate((self._buffer, samples.astype(np.int16, copy=False)))
        matches: list[MatchResult] = []

        while self._buffer.size >= self.window_size:
            window = self._buffer[: self.window_size]
            self._buffer = self._buffer[self.step_size :]
            detected = self._detect_tone(window)
            frame_time = self._stream_time_s + (self.window_size / self.sample_rate)
            match = self._update_state(detected, frame_time)
            if match is not None:
                matches.append(match)
            self._stream_time_s += self.step_size / self.sample_rate

        return matches

    def flush(self) -> MatchResult | None:
        return self._finalize_active_tone()

    def _detect_tone(self, window: np.ndarray) -> float | None:
        rms = float(np.sqrt(np.mean(window.astype(np.float32) ** 2)))
        if rms < self.min_rms:
            return None

        spectrum = np.abs(np.fft.rfft(window * self._window))
        freqs = np.fft.rfftfreq(self.window_size, d=1.0 / self.sample_rate)
        mask = (freqs >= self.min_frequency_hz) & (freqs <= self.max_frequency_hz)
        if not np.any(mask):
            return None

        spectrum = spectrum[mask]
        freqs = freqs[mask]
        peak_index = int(np.argmax(spectrum))
        peak = float(spectrum[peak_index])
        total = float(np.sum(spectrum))
        if total <= 0.0:
            return None

        peak_ratio = peak / total
        if peak_ratio < self.peak_ratio_threshold:
            return None
        return float(freqs[peak_index])

    def _update_state(self, detected_frequency: float | None, frame_time: float) -> MatchResult | None:
        if detected_frequency is None:
            return self._finalize_if_stale(frame_time)

        if self._active_tone is None:
            self._active_tone = _ActiveTone(
                frequency_hz=detected_frequency,
                started_at=frame_time,
                last_seen_at=frame_time,
            )
            return None

        if abs(self._active_tone.frequency_hz - detected_frequency) <= self.frequency_tolerance_hz:
            weighted = (
                (self._active_tone.frequency_hz * self._active_tone.frames) + detected_frequency
            ) / (self._active_tone.frames + 1)
            self._active_tone.frequency_hz = weighted
            self._active_tone.frames += 1
            self._active_tone.last_seen_at = frame_time
            return None

        match = self._finalize_active_tone(frame_time)
        self._active_tone = _ActiveTone(
            frequency_hz=detected_frequency,
            started_at=frame_time,
            last_seen_at=frame_time,
        )
        return match

    def _finalize_if_stale(self, now: float) -> MatchResult | None:
        if self._active_tone is None:
            return None

        stale_after_s = (self.step_size / self.sample_rate) * 2.5
        if now - self._active_tone.last_seen_at >= stale_after_s:
            return self._finalize_active_tone(now)
        return None

    def _finalize_active_tone(self, now: float | None = None) -> MatchResult | None:
        if self._active_tone is None:
            return None

        finished_at = monotonic() if now is None else now
        duration_ms = math.ceil((finished_at - self._active_tone.started_at) * 1000)
        segment = ToneSegment(
            frequency_hz=self._active_tone.frequency_hz,
            duration_ms=duration_ms,
            ended_at=finished_at,
        )
        self._active_tone = None
        return self.matcher.add_segment(segment)
