"""Run with ``uv run python examples/policy.py``; no API key required."""

from jev_lanes import Lanes

lanes = Lanes(auto=0.85, llm=0.60)

for confidence in (0.95, 0.70, 0.40):
    print(f"confidence={confidence:.2f} -> lane={lanes.lane_for(confidence)}")
