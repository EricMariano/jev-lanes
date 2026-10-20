"""Policy boundaries and invalid-input handling, without network access."""

import pytest

from jev_lanes import Lanes


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0, "human"),
        (0.599999, "human"),
        (0.60, "llm"),
        (0.849999, "llm"),
        (0.85, "auto"),
        (1, "auto"),
    ],
)
def test_lane_boundaries(confidence: float, expected: str) -> None:
    assert Lanes(auto=0.85, llm=0.60).lane_for(confidence) == expected


@pytest.mark.parametrize("field", ["auto", "llm"])
@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), -float("inf")])
def test_reject_invalid_threshold_values(field: str, value: float) -> None:
    thresholds = {"auto": 0.85, "llm": 0.60, field: value}
    with pytest.raises(ValueError):
        Lanes(**thresholds)


@pytest.mark.parametrize(("auto", "llm"), [(0.6, 0.6), (0.5, 0.6), (0, 0), (1, 1)])
def test_reject_empty_or_inverted_middle_lane(auto: float, llm: float) -> None:
    with pytest.raises(ValueError, match="llm < auto"):
        Lanes(auto=auto, llm=llm)


@pytest.mark.parametrize("value", [True, False, "0.85", None])
def test_reject_non_numeric_inputs(value: object) -> None:
    with pytest.raises(TypeError):
        Lanes(auto=value, llm=0.60)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Lanes(auto=0.85, llm=value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Lanes(auto=0.85, llm=0.60).lane_for(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), -float("inf")])
def test_invalid_confidence_is_an_error(value: float) -> None:
    with pytest.raises(ValueError):
        Lanes(auto=0.85, llm=0.60).lane_for(value)


def test_extreme_valid_thresholds() -> None:
    lanes = Lanes(auto=1, llm=0)
    assert lanes.lane_for(0) == "llm"
    assert lanes.lane_for(0.999999) == "llm"
    assert lanes.lane_for(1) == "auto"
