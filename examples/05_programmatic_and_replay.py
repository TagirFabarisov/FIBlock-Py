"""Programmatic control: an external search sets fault parameters, and a whole
campaign is exported as plain data and replayed exactly. No optimiser library is
involved; parameters are ordinary attributes."""
import json
import random

from fiblock import At, Bias, Campaign, Fixed, Noise, Uniform


def simulate(campaign):
    """A stand-in for a simulator: returns the worst deviation of a controlled quantity."""
    level, worst = 0.0, 0.0
    for t in range(60):
        campaign.advance(float(t))
        reading = campaign.apply("level_sensor", level)
        command = 1.0 if reading < 5.0 else -1.0   # a bang-bang controller acting on the corrupted reading
        level += 0.5 * command
        worst = max(worst, abs(level - 5.0))
    return worst


bias = Bias("level_sensor", magnitude=0.0, activation=At(10.0), duration=Fixed(20.0), name="sensor_bias")
campaign = Campaign([bias], seed=1)

# 1. an external search proposes candidate magnitudes and keeps the most damaging one
rng = random.Random(0)
best = None
for _ in range(20):
    bias.magnitude = rng.uniform(-3.0, 3.0)      # the search writes the parameter
    campaign.reset()                            # same seed, fresh run
    damage = simulate(campaign)
    if best is None or damage > best[1]:
        best = (bias.magnitude, damage)
print(f"most damaging bias found: magnitude={best[0]:+.3f} -> worst deviation {best[1]:.2f}")

# 2. export the campaign as plain data, rebuild it elsewhere, replay exactly
bias.magnitude = best[0]
campaign.reset()
reference = simulate(campaign)
text = campaign.to_json(indent=1)
replayed = Campaign.from_json(text)
print("replayed worst deviation identical:", simulate(replayed) == reference)
print("\nexported campaign spec:")
print(text)
