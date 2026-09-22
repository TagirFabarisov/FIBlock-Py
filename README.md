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

Requires Python 3.9+ and NumPy.

```bash
pip install -e .            # from a clone of this repository
python -m pytest            # run the tests
```

## Quick start

```python
from fiblock import Campaign, FaultInjector, Bias, PacketLoss, Deterministic, FailureRate, ConstantTime

campaign = Campaign({
    "methane_sensor": FaultInjector(Bias(0.3), Deterministic(120.0), ConstantTime(30.0)),
    "bus":            FaultInjector(PacketLoss(0.5), FailureRate(0.02), ConstantTime(3.0)),
}, seed=42)

for t in times:                                        # the host's own clock, any unit
    campaign.advance(t)                                # fault events, fault effects, triggers
    methane = campaign.apply("methane_sensor", methane_true)
    message = campaign.inject("bus", message_true)     # .value, .missing, .data_error, .caused_by

for record in campaign.log:                            # who, when, why, with which parameters
    print(record)
```

An **injection point** is a name the host chooses: a sensor reading, a
message on a link, a controller word, a pump's capacity parameter. FIBlock
never touches the host's state; the host passes each value through `apply` or
`inject` and receives it as the active faults leave it.

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
