"""Stochastic injection under a seed: the same seed gives the same realisation,
a different seed a different one. Sampled activation times, durations and noise
are recorded in the log."""
from fiblock import (Campaign, ConstantTime, Exponential, FailureRate, FailureTimeDistribution, FaultInjector,
                     MeanTimeToRepair, Noise, PacketLoss, Weibull)


def build():
    return {
        # wear-out activation (Weibull shape > 1), repaired after a mean time of 10, then it can happen again
        "methane_sensor": FaultInjector(Noise(0.2), FailureTimeDistribution(Weibull(shape=2.0, scale=50.0), repeat=True),
                                        MeanTimeToRepair(10.0), name="noisy_methane"),
        # constant failure rate of 0.02 per second on the bus; each burst drops every packet for 3 s
        "bus": FaultInjector(PacketLoss(), FailureRate(0.02), ConstantTime(3.0), name="bus_drop"),
    }


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
print("\nInjection log for seed 42:")
for record in c1.log:
    print(" ", record)
