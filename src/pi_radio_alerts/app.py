from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

from .config import load_sequences
from .detector import QuickCallDetector
from .display import DisplayController
from .matcher import SequenceMatcher
from .sdr import RtlFmSource


LOG = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor Quick Call II alerts on an RTL-SDR.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[2] / "tones.json"),
        help="Path to the tone sequence JSON file.",
    )
    parser.add_argument("--frequency-mhz", type=float, default=153.89)
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--gain", default="auto")
    parser.add_argument("--squelch", type=int, default=0)
    parser.add_argument("--hold-seconds", type=int, default=120)
    parser.add_argument("--hardware-mapping", default="adafruit-hat-pwm")
    parser.add_argument("--brightness", type=int, default=40)
    parser.add_argument("--wav-file", help="Optional WAV file for offline testing.")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sequences = load_sequences(args.config)
    matcher = SequenceMatcher(sequences)
    detector = QuickCallDetector(matcher, sample_rate=args.sample_rate)
    display = DisplayController(
        hold_seconds=args.hold_seconds,
        hardware_mapping=args.hardware_mapping,
        brightness=args.brightness,
    )
    source = RtlFmSource(
        frequency_mhz=args.frequency_mhz,
        sample_rate=args.sample_rate,
        gain=args.gain,
        squelch=args.squelch,
        wav_file=args.wav_file,
    )

    shutdown = False

    def handle_signal(_signum: int, _frame: object) -> None:
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    display.start()
    try:
        for samples in source.sample_stream():
            for match in detector.feed(samples):
                LOG.info("Matched alert: %s", match.sequence.name)
                display.show_alert(match.sequence.name)
            if shutdown:
                break
    except FileNotFoundError as exc:
        display.set_error("ERROR")
        LOG.error("rtl_fm was not found: %s", exc)
        return 1
    except Exception:
        display.set_error("ERROR")
        LOG.exception("Unhandled runtime error")
        return 1
    finally:
        final_match = detector.flush()
        if final_match is not None:
            LOG.info("Matched alert: %s", final_match.sequence.name)
            display.show_alert(final_match.sequence.name)
        display.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
