from pi_radio_alerts.config import ToneSequence, ToneSpec
from pi_radio_alerts.matcher import SequenceMatcher, ToneSegment


def test_matches_two_tone_sequence() -> None:
    matcher = SequenceMatcher(
        [
            ToneSequence(
                name="PHOENIX GENERAL",
                tones=(
                    ToneSpec(frequency_hz=617.4, duration_ms=1000),
                    ToneSpec(frequency_hz=483.5, duration_ms=3000),
                ),
            )
        ]
    )

    assert matcher.add_segment(ToneSegment(frequency_hz=617.0, duration_ms=950, ended_at=1.0)) is None
    match = matcher.add_segment(ToneSegment(frequency_hz=483.0, duration_ms=3050, ended_at=4.1))

    assert match is not None
    assert match.sequence.name == "PHOENIX GENERAL"


def test_rejects_wrong_order() -> None:
    matcher = SequenceMatcher(
        [
            ToneSequence(
                name="RIVERDALE STILL",
                tones=(
                    ToneSpec(frequency_hz=1153.0, duration_ms=1000),
                    ToneSpec(frequency_hz=1063.0, duration_ms=3000),
                ),
            )
        ]
    )

    assert matcher.add_segment(ToneSegment(frequency_hz=1063.0, duration_ms=3000, ended_at=1.0)) is None
    match = matcher.add_segment(ToneSegment(frequency_hz=1153.0, duration_ms=1000, ended_at=2.1))

    assert match is None
