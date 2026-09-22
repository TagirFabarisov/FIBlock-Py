"""Deterministic injection: a methane sensor reads 0.3 too high from t=120 s for 30 s,
and the water-level sensor freezes at t=140 s for 10 s. Nothing here is random."""
from fiblock import Bias, Campaign, ConstantTime, Deterministic, FaultInjector, Freeze

campaign = Campaign({
    "methane_sensor": FaultInjector(Bias(0.3), Deterministic(120.0), ConstantTime(30.0), name="methane_bias"),
    "water_sensor": FaultInjector(Freeze(), Deterministic(140.0), ConstantTime(10.0), name="water_freeze"),
})

dt = 10.0
for step in range(20):
    t = step * dt
    methane_true = 1.0                      # what the physics says
    water_true = 2.0 + 0.05 * step         # slowly rising level
    campaign.advance(t)                     # fault events and fault effects are evaluated here
    methane_read = campaign.apply("methane_sensor", methane_true)
    water_read = campaign.apply("water_sensor", water_true)
    print(f"t={t:5.0f}  methane true={methane_true:.2f} read={methane_read:.2f}   water true={water_true:.2f} read={water_read:.2f}")

print("\nInjection log:")
for record in campaign.log:
    print(" ", record)
