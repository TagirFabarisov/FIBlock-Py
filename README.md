# FIBlock

```python
from fiblock import Bias, Drift, Noise, Freeze, Delay, PacketLoss
```

FIBlock is a model-based fault-injection framework for cyber-physical
systems. This repository is its Python implementation. It provides a
programmable API for deterministic, stochastic, and algorithmically
controlled injection of faults across heterogeneous CPS components: sensing,
computation and control, communication, and physical elements.

The original FIBlock is a MATLAB/Simulink block library:
**https://github.com/TagirFabarisov/FIBlock**. The Python version is written
from scratch and keeps the structure of the original block. A fault injector
combines three independent choices: a **fault type** (what the error looks
like, with its fault value), a **fault event** (when the fault activates) and
a **fault effect** (how long it lasts). A **trigger input** overrules the
event, so that one fault can force another (chained fault injection).
Injectors can be enabled one by one and placed at many injection points at
once; every activation is recorded. Users add their own fault types by
subclassing.

If you use FIBlock, please cite the original paper (see [Citation](#citation)).

## Installation

Requires Python 3.9+ and NumPy. From a clone of this repository:

```bash
python -m pip install --upgrade pip   # an editable install of a pyproject-only package needs pip 21.3 or newer
pip install -e .
python -m pytest                      # run the tests
```

Without installing, the examples and tests also run with `PYTHONPATH=src`.

## Quick start

Run the smallest example and read it:

```bash
python examples/00_minimal_noise.py
```

FIBlock connects to a system at one kind of place: between a value and
whoever consumes it, where a FIBlock block would sit on a Simulink signal
line. You give that place a name, an **injection point**, and route the value
through FIBlock there. Two calls do it: `advance(t)` once per step, so that
fault events and fault effects can act, and `apply(point, value)` where the
value passes. What comes back is what the rest of the system sees. The
system itself is not changed.

```python
from fiblock import Campaign, ConstantTime, Deterministic, FaultInjector, Noise

# --- your system, unchanged: a tank whose temperature sensor feeds a thermostat
temperature = 20.0

def thermostat(reading):
    return reading < 21.0          # heater on below 21 degrees

# --- FIBlock: one injection point named "temp_sensor", one injector on it
campaign = Campaign({
    "temp_sensor": FaultInjector(
        Noise(value=0.5),          # what: gaussian noise, amplitude 0.5 degrees
        Deterministic(time=3.0),   # when: from t = 3
        ConstantTime(value=4.0),   # how long: for 4 time units
    ),
}, seed=1)

# --- your loop, with the two FIBlock calls inserted
for t in range(10):
    campaign.advance(t)                                   # (1) fault events and effects act
    reading = campaign.apply("temp_sensor", temperature)  # (2) the sensor value passes the point
    heater_on = thermostat(reading)                       # the controller sees the corrupted reading
    temperature += 0.3 if heater_on else -0.3             # your physics, untouched
    print(f"t={t}  true={temperature:5.2f}  sensor reads={reading:5.2f}  heater={'on' if heater_on else 'off'}")

for record in campaign.log:                               # what FIBlock did
    print(record)
```

```
t=0  true=20.30  sensor reads=20.00  heater=on
t=1  true=20.60  sensor reads=20.30  heater=on
t=2  true=20.90  sensor reads=20.60  heater=on
t=3  true=21.20  sensor reads=19.58  heater=on      <- noise starts
t=4  true=20.90  sensor reads=21.87  heater=off
t=5  true=21.20  sensor reads=20.71  heater=on
t=6  true=21.50  sensor reads=20.70  heater=on
t=7  true=21.20  sensor reads=21.50  heater=off     <- fault effect over, on time again
t=8  true=20.90  sensor reads=21.20  heater=off
t=9  true=21.20  sensor reads=20.90  heater=on
t=3 activation    Noise@temp_sensor#0 (Noise on temp_sensor) via Deterministic sampled={'activation_time': 3.0, 'scheduled_time': 3.0, 'duration': 4.0}
t=7 deactivation  Noise@temp_sensor#0 (Noise on temp_sensor) via expired
```

Between t = 3 and t = 7 the thermostat acts on a noisy reading and switches
at the wrong moments; before and after, it sees the true value. The two lines
at the end are FIBlock's own record of the fault.

An injection point can be anything the host reads each step: a sensor
reading, a message on a link, a controller word, a pump's capacity parameter
(route the capacity through a point with a `Gain(0.6)` on it and the pump
runs at 60 % while the fault is active). A campaign maps each point to one
injector or a list of them; a single injector can also run on its own
(`FaultInjector(..., seed=1)`, then `step(t)` and `inject(value)`). The other
scripts in [`examples/`](examples/README.md) build up from here.

## How the library is organised

```
FaultInjector( fault type , fault event , fault effect , trigger= )
               what        when          how long      forced by another injector
```

| Package | Role |
|---|---|
| `fiblock.core` | the mechanism: `FaultInjector` with its `Trigger` input, the base classes `FaultType`, `FaultEvent` and `FaultEffect`, the records it produces, specs and random streams |
| `fiblock.types` | fault types, one module each |
| `fiblock.events` | fault events, one module each |
| `fiblock.effects` | fault effects, one module each |
| `fiblock.distributions` | probability distributions used by events, effects and types |
| `fiblock.campaign` | `Campaign`: injection points, one seed, one clock, delivery of activations to trigger inputs, export and replay |
| `fiblock.logger` | `InjectionLog`: the evidence, fault-injection records and data-error records |

Dependencies point one way: the campaign uses the core, the core knows only
the three base classes, and a fault type never sees an event or an effect.
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) has the diagram, the dependency
rules and the map from the original block's terms to the Python names.

## Fault types

By FIBlock convention the main parameter of every type is its `value`, the
"fault value".

| Fault type | Effect on the value |
|---|---|
| `Bias(value, relative=False)` | add a constant, or multiply by `1 + value` |
| `Drift(value, relative=False)` | offset growing linearly with time since activation (`value` = slope) |
| `Noise(value, relative=False, distribution=Normal(0, 1))` | add `value × sample`; `relative=True` with `Uniform(-1, 1)` is the original block's noise within a fraction of the correct value |
| `Gain(value)` | multiply: the gain / scaling fault of the sensor-fault literature, the loss of effectiveness of the actuator literature |
| `Freeze()` | hold the last correct value seen before activation |
| `StuckAt(value)` | replace by a constant |
| `BitFlip(value=1, width=None)` | invert `value` random bits of the binary word (float, int, bool, one element of an array) |
| `Delay(value, gap="missing")` | values arrive `value` time units late; before the first late value is due nothing arrives (or the last correct value, with `gap="hold"`) |
| `PacketLoss(value=1.0, substitute=MISSING)` | drop each value with probability `value` |

`Delay` and `PacketLoss` may return `fiblock.MISSING`, a sentinel meaning
*nothing arrived*. What the receiver does with a missing value, hold the
previous one, substitute a default, switch to a safe mode, is the receiver's
design decision, not the fault's. `Outcome.missing` tells the host.

## Fault events

Time is the host's time in the host's units.

| Fault event | When the fault activates |
|---|---|
| `Deterministic(time=0.0)` | at a fixed time (default: immediately) |
| `FailureProbability(value)` | with a fixed probability at every step (step-size dependent, as in the original block) |
| `MeanTimeToFailure(value, spread=None, repeat=True)` | after a random time with mean `value`: exponential by default, normal with `spread` as in the original; with `repeat` a new time is drawn after each deactivation |
| `FailureTimeDistribution(distribution, repeat=False)` | after a random time from any distribution (Weibull for wear-out, a two-Weibull `Mixture`, ...) |
| `FailureRate(value)` | with a hazard rate per unit time, independent of the step size; `value` may be a number, a `TabulatedRate(times, rates)` curve (the hand-drawn "manual distribution" of the original) or a callable of time |
| `Never()` | only through the trigger input or an explicit `campaign.activate(...)` |

## Fault effects

| Fault effect | How long the fault stays active |
|---|---|
| `Once()` | a single step |
| `ConstantTime(value)` | a fixed duration |
| `InfiniteTime()` | until the end of the run |
| `MeanTimeToRepair(value, spread=None)` | a random duration with mean `value` (exponential, or normal with `spread`) |
| `DurationDistribution(distribution)` | a random duration from any distribution |

`campaign.activate(name)` and `campaign.deactivate(name)` override any event
or effect.

## Distributions

Any place that draws a time, a duration, a delay or a noise sample takes a
distribution object: `Constant`, `Uniform`, `Normal`, `LogNormal`,
`Exponential`, `Weibull`, `Gamma`, `Choice`, `Empirical`, `Mixture`, a bare
number, any callable `rng -> float`, or a SciPy frozen distribution. This is
what lets different degradation scenarios be expressed: a wear-out
activation is a Weibull with shape above one, an infant-mortality one a shape
below one, a two-population component a `Mixture` of two Weibulls.

## The trigger input and chained faults

As in the original block, every injector has a trigger input that overrules
its fault event: when the trigger fires, the fault activates whatever the
event's parameters say. Wiring one injector's activation to another's trigger
input is chained fault injection:

```python
flip = FaultInjector(BitFlip(1), Deterministic(5.0), Once(), name="flip")
late = FaultInjector(Delay(1.0), Never(), ConstantTime(4.0), trigger=Trigger(by=flip, delay=2.0))
drop = FaultInjector(PacketLoss(0.5), Never(), ConstantTime(4.0), trigger=Trigger(by=late))
```

`Trigger(by, delay=0.0, probability=1.0, repeat=True)`. An injector may keep
its own event and also be triggered; `Never()` is the event of an injector
that only ever activates through its trigger or by hand. The campaign hands
every activation record to every trigger input; chains resolve within the
same step, in any order of declaration, and the log records the source of
every triggered activation. `campaign.activate(name)` drives the trigger
input from the host.

## Campaigns, seeds and replay

A campaign wires injectors to named injection points under one seed and one
clock. Each injector draws from its own random stream, derived from the
campaign seed and the injector's name, so adding, removing or reordering
other injectors does not change its draws. A campaign built without a seed
draws one and keeps it; `campaign.seed` can always be stored.
`campaign.reset()` replays the same realisation, `campaign.reset(seed=...)`
gives a new one. An injector can also run on its own:
`FaultInjector(..., seed=1)`, then `step(t)` and `inject(value)`.

Fault parameters are plain attributes, so any external program can set them:

```python
bias = Bias(0.0)
campaign = Campaign({"level_sensor": FaultInjector(bias, Deterministic(10.0), ConstantTime(20.0))}, seed=1)
for candidate in search.propose():
    bias.value = candidate                 # the search writes the fault value
    campaign.reset()                       # same seed, fresh run
    result = simulate(campaign)
```

A campaign exports itself as plain data with `campaign.spec()` or
`campaign.to_json()` and is rebuilt with `Campaign.from_spec` or
`Campaign.from_json`; with the same seed the rebuilt campaign replays the
original exactly. Callables (a `FromCallable` distribution, a callable rate)
are recorded by their `repr` and must be supplied again in code.

## Faults, data errors and the log

FIBlock injects **faults**. Whether an active fault produces an **error** in
the data is a separate matter: a packet-loss fault active with probability
0.5 corrupts only some values, a freeze corrupts none until a value arrives.
The injection mechanism knows only faults; its records are fault activations
and deactivations. The campaign additionally compares the value before and
after each injection point and reports the result in the `Outcome`: `active`
(which injectors were active), `data_error` (the value differs from the
correct one) and `caused_by` (which of them changed it).

Every fault activation and deactivation is an `InjectionRecord` with the
injector's name, the fault type, the injection point, the time, the
configured parameters, the values sampled at run time (scheduled time,
duration, delay, trigger source, ...), the cause (`Deterministic`,
`FailureRate`, `trigger:<injector>`, `manual`, `expired`, ...) and the seed
provenance. With `Campaign(..., record_data_errors=True)` every observed data
error is stored as well, as a `DataErrorRecord` with the value before and
after and the injectors that caused it, so that the evidence exists for later
analysis. `campaign.log.faults()`, `.data_errors()`,
`.filter(kind=..., injector=..., point=...)`, `.counts()`, `.to_dicts()` and
`.to_json()` are available, and a shared `InjectionLog` can be passed in.

## Custom fault types

```python
from fiblock import FaultType, register

@register                                    # optional: makes it rebuildable from a spec
class Saturation(FaultType):
    def __init__(self, value, decay_rate=0.0):   # value = the fault value
        self.value = value
        self.decay_rate = decay_rate

    def apply(self, value, ctx):             # ctx.t, ctx.dt, ctx.elapsed, ctx.rng, ctx.host
        return min(value, self.value - self.decay_rate * (ctx.elapsed or 0.0))
```

Constructor arguments become the fault's parameters: plain attributes,
reported in every record and in the spec. Optional hooks: `observe` (sees
every pre-fault value, active or not), `on_activate` (may return sampled
values to record), `on_deactivate` and `reset`. A fault type only produces the
corrupted value; whether that counts as a data error is judged outside it.
Fault events and fault effects are extended the same way, from `FaultEvent`
and `FaultEffect`.

## Scope

FIBlock introduces faults at injection points chosen by the host and records
what it did. It does not model how an error propagates from an injection
point through the rest of a system, and it does not decide what a
system-level failure is; both belong to the model of the system under study.
FIBlock makes no assumptions about that system: what is being simulated, how
its time advances, how its control is organised, which program chooses the
fault parameters, or what is done with the records. It is a library the host
calls, not a framework the host has to fit into.

## Examples

- `examples/01_deterministic.py` — scheduled faults, no randomness
- `examples/02_stochastic_seeded.py` — Weibull activation and mean time to repair, seed replay
- `examples/03_custom_fault_type.py` — a user-defined fault type
- `examples/04_chained_faults.py` — a four-injector chain through trigger inputs, with the log
- `examples/05_programmatic_and_replay.py` — an external search setting the fault value, export and exact replay

## Citation

> T. Fabarisov, I. Mamaev, A. Morozov, and K. Janschek,
> "Model-based Fault Injection Experiments for the Safety Analysis of
> Exoskeleton System," *Proceedings of ESREL 2020 / PSAM 15*, 2020.
> arXiv:[2101.01283](https://arxiv.org/abs/2101.01283).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
