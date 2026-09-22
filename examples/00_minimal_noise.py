"""The smallest possible use: noise on one sensor of a system you already have.

FIBlock sits between the true value and whoever consumes it, exactly where
a FIBlock block would sit on a Simulink signal line. Two calls connect it:
``advance(t)`` once per step, and ``apply(point, value)`` where the value passes.
"""
from fiblock import Campaign, ConstantTime, Deterministic, FaultInjector, Noise

# --- your system, unchanged: a tank whose temperature sensor feeds a thermostat -----------
temperature = 20.0
heater_on = False


def thermostat(reading):
    return reading < 21.0          # switch the heater on below 21 degrees


# --- FIBlock: one injection point named "temp_sensor", one injector on it ----------------
campaign = Campaign({
    "temp_sensor": FaultInjector(
        Noise(value=0.5),          # what: gaussian noise with amplitude 0.5 degrees
        Deterministic(time=3.0),   # when: from t = 3
        ConstantTime(value=4.0),   # how long: for 4 time units
    ),
}, seed=1)

# --- the simulation loop, with the two FIBlock calls inserted ----------------------------
for t in range(10):
    campaign.advance(t)                                   # (1) let fault events and effects act
    reading = campaign.apply("temp_sensor", temperature)  # (2) the sensor value passes the injection point
    heater_on = thermostat(reading)                       # your controller sees the (possibly) corrupted reading
    temperature += 0.3 if heater_on else -0.3             # your physics, untouched
    print(f"t={t}  true={temperature:5.2f}  sensor reads={reading:5.2f}  heater={'on ' if heater_on else 'off'}")

print()
for record in campaign.log:
    print(record)
