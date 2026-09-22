"""Chained faults through the trigger input: a bus delay is forced 2 s after a
controller bit flip; the delay's activation forces packet loss on the same
bus; the packet loss forces a one-step spike on the actuator command. A
trigger overrules the injector's own fault event (here ``Never``: no event of
its own). Data errors are observed per value: the packet loss is active for
4 s but drops only some packets."""
from fiblock import (Bias, BitFlip, Campaign, ConstantTime, Delay, Deterministic, FaultInjector, Never, Once, PacketLoss,
                     Trigger)

flip = FaultInjector(BitFlip(1), Deterministic(5.0), Once(), name="flip")
late = FaultInjector(Delay(1.0), Never(), ConstantTime(4.0), trigger=Trigger(by=flip, delay=2.0), name="late")
drop = FaultInjector(PacketLoss(0.5), Never(), ConstantTime(4.0), trigger=Trigger(by=late), name="drop")
spike = FaultInjector(Bias(5.0), Never(), Once(), trigger=Trigger(by=drop), name="spike")

campaign = Campaign({"controller_word": flip, "bus": [late, drop], "actuator_cmd": spike}, seed=3, record_data_errors=True)
for t in range(14):
    campaign.advance(float(t))
    word = campaign.apply("controller_word", 1024)
    bus = campaign.inject("bus", float(t))
    cmd = campaign.apply("actuator_cmd", 1.0)
    print(f"t={t:2d}  word={word:<8} bus={bus.value!s:<8} active={bus.active!s:<18} data error caused by={bus.caused_by!s:<18} cmd={cmd}")

print("\nFault-injection records (the causal chain):")
for record in campaign.log.faults():
    print(" ", record)
print("\nData-error records on the bus:")
for record in campaign.log.data_errors().filter(point="bus"):
    print(" ", record)
