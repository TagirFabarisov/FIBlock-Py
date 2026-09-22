"""A user-defined fault type: a sensor whose reading saturates at a ceiling that
drops over time (a clogging intake, say). Only `apply` is needed; activation,
duration, seeding, chaining, records and replay come from the library."""
from fiblock import Campaign, ConstantTime, Deterministic, FaultInjector, FaultType, register


@register                      # optional: lets Campaign.from_spec rebuild it by name
class Saturation(FaultType):
    def __init__(self, value, decay_rate=0.0):   # value = the ceiling (the fault value)
        self.value = value
        self.decay_rate = decay_rate

    def apply(self, value, ctx):
        limit = self.value - self.decay_rate * (ctx.elapsed or 0.0)
        return min(value, limit)


campaign = Campaign({"flow_sensor": FaultInjector(Saturation(8.0, decay_rate=0.5), Deterministic(3.0), ConstantTime(6.0))})
for t in range(10):
    campaign.advance(float(t))
    print(f"t={t}  true=10.0  read={campaign.apply('flow_sensor', 10.0):.1f}")
print(campaign.log[0])
print("spec of the injector:", campaign.spec()["points"]["flow_sensor"][0])
