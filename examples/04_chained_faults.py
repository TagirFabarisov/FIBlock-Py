"""Chained (conditional) faults: a bus delay is triggered 2 s after a controller
bit-flip; while the bus is delayed, every dropped packet also spikes the actuator
command. Triggers can fire on activation, manifestation or deactivation."""
from fiblock import At, BitFlip, Bias, Campaign, Delay, Fixed, Once, PacketLoss, Triggered

flip = BitFlip("controller_word", bits=1, activation=At(5.0), duration=Once(), name="flip")
late = Delay("bus", delay=1.0, activation=Triggered(by=flip, on="activated", delay=2.0), duration=Fixed(4.0), name="late")
drop = PacketLoss("bus", probability=0.5, activation=Triggered(by=late, on="activated"), duration=Fixed(4.0), name="drop")
spike = Bias("actuator_cmd", magnitude=5.0, activation=Triggered(by=drop, on="manifested"), duration=Once(), name="spike")

campaign = Campaign([flip, late, drop, spike], seed=3)
for t in range(14):
    campaign.advance(float(t))
    word = campaign.apply("controller_word", 1024)
    bus = campaign.inject("bus", float(t))
    cmd = campaign.apply("actuator_cmd", 1.0)
    print(f"t={t:2d}  word={word:<6} bus={bus.value!s:<8} manifested={bus.manifested!s:<20} cmd={cmd}")

print("\nCausal record:")
for e in campaign.events:
    print(" ", e)
