from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import logging
import subprocess

import numpy as np


LOG = logging.getLogger(__name__)


class RtlFmSource:
    def __init__(
        self,
        *,
        frequency_mhz: float = 153.89,
        sample_rate: int = 22050,
        gain: str = "auto",
        squelch: int = 0,
        executable: str = "rtl_fm",
        read_size: int = 4096,
        wav_file: str | None = None,
    ) -> None:
        self.frequency_mhz = frequency_mhz
        self.sample_rate = sample_rate
        self.gain = gain
        self.squelch = squelch
        self.executable = executable
        self.read_size = read_size
        self.wav_file = wav_file

    def sample_stream(self) -> Iterator[np.ndarray]:
        if self.wav_file:
            yield from self._wav_stream()
            return

        cmd = [
            self.executable,
            "-f",
            f"{self.frequency_mhz}M",
            "-M",
            "fm",
            "-s",
            str(self.sample_rate),
            "-g",
            str(self.gain),
            "-l",
            str(self.squelch),
            "-E",
            "deemp",
            "-F",
            "9",
            "-",
        ]
        LOG.info("Starting rtl_fm: %s", " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

        try:
            assert process.stdout is not None
            while True:
                chunk = process.stdout.read(self.read_size)
                if not chunk:
                    break
                yield np.frombuffer(chunk, dtype=np.int16)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)

        if process.returncode not in (0, None, -15):
            raise RuntimeError(f"rtl_fm exited with code {process.returncode}")

    def _wav_stream(self) -> Iterator[np.ndarray]:
        import wave

        path = Path(self.wav_file)
        LOG.info("Reading samples from %s", path)
        with wave.open(str(path), "rb") as handle:
            while True:
                frames = handle.readframes(self.read_size // 2)
                if not frames:
                    break
                yield np.frombuffer(frames, dtype=np.int16)
