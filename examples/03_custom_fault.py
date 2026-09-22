"""A user-defined fault: a sensor whose reading saturates at a ceiling that
drops over time (a clogging intake, say). Only `apply` is needed; activation,
duration, seeding, chaining, events and replay come from the library."""
from fiblock import At, Campaign, Fault, Fixed, register


@register                      # optional: lets Campaign.from_spec rebuild it by name
class Saturation(Fault):
    def __init__(self, target, ceiling, decay_rate=0.0, **kw):
        super().__init__(target, **kw)
        self.ceiling = ceiling
        self.decay_rate = decay_rate

    def apply(self, value, ctx):
        limit = self.ceiling - self.decay_rate * (ctx.elapsed or 0.0)
        return min(value, limit)


campaign = Campaign([Saturation("flow_sensor", ceiling=8.0, decay_rate=0.5, activation=At(3.0), duration=Fixed(6.0))])
for t in range(10):
    campaign.advance(float(t))
    print(f"t={t}  true=10.0  read={campaign.apply('flow_sensor', 10.0):.1f}")
print(campaign.events[0])
print("spec of the custom fault:", campaign.spec()["faults"][0])
