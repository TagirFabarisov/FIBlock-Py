"""Stochastic injection under a seed: the same seed gives the same realisation,
a different seed a different one. Activation times, durations and noise samples
are all recorded in the events."""
from fiblock import Campaign, Exponential, Noise, PacketLoss, Rate, SampledDuration, SampledTime, Weibull, Fixed


def build():
    return [
        # wear-out style activation (Weibull shape > 1), repaired after an exponential time, then it can happen again
        Noise("methane_sensor", amplitude=0.2, activation=SampledTime(Weibull(shape=2.0, scale=50.0), repeat=True),
              duration=SampledDuration(Exponential(rate=0.1)), name="noisy_methane"),
        # constant hazard rate of 0.02 per second on the bus; each burst drops every packet for 3 s
        PacketLoss("bus", activation=Rate(0.02), duration=Fixed(3.0), name="bus_drop"),
    ]


def run(seed):
    campaign = Campaign(build(), seed=seed)
    trace = []
    for t in range(0, 200):
        campaign.advance(float(t))
        trace.append((campaign.apply("methane_sensor", 1.0), campaign.apply("bus", t)))
    return campaign, trace


c1, t1 = run(seed=42)
c2, t2 = run(seed=42)
c3, t3 = run(seed=43)
print("seed 42 twice identical:", t1 == t2)
print("seed 42 vs 43 identical:", t1 == t3)
print("\nEvents for seed 42:")
for e in c1.events:
    print(" ", e)
