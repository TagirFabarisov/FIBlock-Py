# FIBlock

```python
from fiblock import Bias, Drift, Noise, Freeze, Delay, PacketLoss
```

FIBlock is a model-based fault-injection framework for cyber-physical systems.
This repository is its Python implementation. It provides a programmable API
for deterministic, stochastic, and algorithmically controlled injection of
faults across heterogeneous CPS components: sensing, computation and control,
communication, and physical elements.

The original FIBlock is a MATLAB/Simulink block library:
**https://github.com/TagirFabarisov/FIBlock**. The Python version is written
from scratch and keeps the FIBlock idea: a fault is attached to a point in the
system and described by independent, freely combinable choices of *what the
error looks like*, *when it activates*, and *how long it lasts*; faults can be
enabled one by one, injected at many points at once, and chained so that one
fault triggers another; every activation is recorded with its parameters.
Each built-in fault type lives in its own module under `fiblock/faults/`; users add their own fault types the same way, by subclassing.

If you use FIBlock, please cite the original paper (see [Citation](#citation)).

## Installation

Requires Python 3.9+ and NumPy.

```bash
pip install -e .            # from a clone of this repository
python -m pytest            # run the tests
```

## Quick start

```python
from fiblock import Campaign, Bias, PacketLoss, At, Fixed, Rate

campaign = Campaign([
    Bias("methane_sensor", magnitude=0.3, activation=At(120.0), duration=Fixed(30.0)),
    PacketLoss("bus", probability=0.5, activation=Rate(0.02), duration=Fixed(3.0)),
], seed=42)

for t in times:                                   # the host's own clock, any unit
    campaign.advance(t)                           # activations, expiries, chained triggers
    methane = campaign.apply("methane_sensor", methane_true)
    message = campaign.inject("bus", message_true)  # .value, .missing, .manifested
    ...

for event in campaign.events:                     # who, when, why, with which parameters
    print(event)
```

A fault has a **target**, a string the host chooses for an injection point:
a sensor reading, a message on a link, a controller word, a pump's capacity
parameter. FIBlock never touches simulator state; the host passes each value
through `apply` or `inject` and receives it as the active faults leave it.

## The three choices

| Choice | Question | Built-in options |
|---|---|---|
| Fault type | what does the error look like? | `Bias`, `Drift`, `Noise`, `Scale`, `Freeze`, `StuckAt`, `BitFlip`, `Delay`, `PacketLoss`, or your own |
| Activation | when does it start? | `Immediately`, `At(t)`, `SampledTime(dist)`, `Rate(λ)`, `PerStep(p)`, `When(condition)`, `Triggered(by=...)`, `Never` |
| Duration | how long does it last? | `Once`, `Fixed(d)`, `Permanent`, `SampledDuration(dist)`, `Until(condition)`, plus explicit `campaign.deactivate(...)` |

Any type combines with any activation and any duration. Distributions
(`Uniform`, `Normal`, `Exponential`, `Weibull`, `Gamma`, `LogNormal`,
`Mixture`, `Choice`, `Empirical`, a bare number, any callable `rng -> float`,
or a SciPy frozen distribution) are accepted wherever a time, duration,
delay or noise sample is drawn.

### Fault types

| Fault | Effect on the value |
|---|---|
| `Bias(magnitude, relative=False)` | add a constant, or multiply by `1 + magnitude` |
| `Drift(rate, relative=False)` | offset growing linearly with time since activation |
| `Noise(amplitude, relative=False, distribution=Normal(0, 1))` | add `amplitude × sample`; `relative=True` with `Uniform(-1, 1)` gives the original FIBlock's percentage noise |
| `Scale(factor)` | multiply (a pump at 60 % capacity) |
| `Freeze()` | hold the last correct value seen before activation |
| `StuckAt(value)` | replace by a constant |
| `BitFlip(bits=1, width=None)` | invert random bits of the binary word (float, int, bool, one element of an array) |
| `Delay(delay, gap="missing")` | values arrive `delay` time units late; before the first late value is due, nothing arrives (or the last correct value, with `gap="hold"`) |
| `PacketLoss(probability=1.0, substitute=MISSING)` | drop each value with the given probability |

`Delay` and `PacketLoss` may return `fiblock.MISSING`, a sentinel meaning
*nothing arrived*. What the receiver does with a missing value, hold the
previous one, substitute a default, switch to a safe mode, is the receiver's
design decision, not the fault's. `Outcome.missing` tells the host.

### Activation

Time is the host's time in the host's units. `Rate(λ)` activates with
probability `1 − exp(−λ·dt)` over each advance, so it does not depend on the
step size; `λ` may be a number, a `TabulatedRate(times, rates)` curve, or a
callable of time. `PerStep(p)` is the step-dependent probability of the
original FIBlock, kept for continuity. `SampledTime(dist, repeat=True)` is the
mean-time-to-failure cycle: a new activation time is drawn after every
deactivation. `When(condition)` evaluates `condition(ctx)` at every advance,
with `ctx.host` being whatever object the host passes to `advance`.

### Chained faults

```python
flip = BitFlip("controller_word", activation=At(5.0), duration=Once(), name="flip")
late = Delay("bus", delay=1.0, activation=Triggered(by=flip, on="activated", delay=2.0), duration=Fixed(4.0))
spike = Bias("actuator_cmd", 5.0, activation=Triggered(by="drop", on="manifested"), duration=Once())
```

`Triggered` fires on another fault's `activated`, `manifested` (it actually
altered a value) or `deactivated` event, after an optional delay (a number or
a distribution), with an optional probability. Chains resolve within the same
step, in any order of declaration, and the event log records the source of
every triggered activation.

### Custom faults

```python
from fiblock import Fault, register

@register                                    # optional: makes it rebuildable from a spec
class Saturation(Fault):
    def __init__(self, target, ceiling, **kw):
        super().__init__(target, **kw)
        self.ceiling = ceiling

    def apply(self, value, ctx):             # ctx.t, ctx.dt, ctx.elapsed, ctx.rng, ctx.host
        return min(value, self.ceiling)
```

Constructor parameters become the fault's parameters: plain attributes,
reported in every event and in the spec. Optional hooks: `observe` (sees every
pre-fault value, active or not), `on_activate` (may return sampled values to
record), `on_deactivate`, `reset`, and `manifests` (what counts as an error).

## Parameters are plain data

```python
fault = Bias("level_sensor", magnitude=0.0, activation=At(10.0), duration=Fixed(20.0))
campaign = Campaign([fault], seed=1)
for candidate in search.propose():
    fault.magnitude = candidate            # any external program may set parameters
    campaign.reset()                       # same seed, fresh run
    result = simulate(campaign)
```

Nothing in FIBlock knows which program chose the parameters. A campaign
exports itself as plain data with `campaign.spec()` / `campaign.to_json()`
and is rebuilt with `Campaign.from_spec` / `Campaign.from_json`; with the same
seed the rebuilt campaign replays the original exactly. Callable conditions
(`When`, `Until`, `FromCallable`) are recorded by their `repr` and must be
supplied again in code.

## Seeds and reproducibility

Each fault draws from its own random stream, derived from the campaign seed
and the fault's name. Adding, removing or reordering other faults does not
change a fault's draws. A campaign built without a seed draws one from the
operating system and keeps it, so `campaign.seed` can always be stored and
replayed. `campaign.reset()` replays; `campaign.reset(seed=...)` gives a new
realisation.

## Events

Every activation and deactivation is a `FaultEvent` with the fault's name and
type, the target, the time, the configured parameters, the values sampled at
run time (activation time, duration, delay, trigger source and delay, ...),
the cause (`At`, `Rate`, `trigger:<fault>`, `manual`, `expired`, ...) and the
seed provenance. With `Campaign(..., record_manifestations=True)` every
manifested error is recorded too, with the value before and after.
`campaign.events.filter(kind=..., fault=..., target=...)`, `.counts()`,
`.to_dicts()` and `.to_json()` are available.

## What FIBlock does not do

FIBlock introduces a fault's effect at the selected injection point. It does
not model how the resulting error propagates through the rest of a system,
nor what the system-level consequence is; that is the host simulator's job.
FIBlock is independent of any simulator, control loop, time step, Gymnasium
environment or optimisation library.

## Examples

- `examples/01_deterministic.py` — scheduled faults, no randomness
- `examples/02_stochastic_seeded.py` — Weibull/exponential activation and repair, seed replay
- `examples/03_custom_fault.py` — a user-defined fault
- `examples/04_chained_faults.py` — a four-fault causal chain with the event record
- `examples/05_programmatic_and_replay.py` — an external search setting parameters, spec export and exact replay

## Citation

> T. Fabarisov, I. Mamaev, A. Morozov, and K. Janschek,
> "Model-based Fault Injection Experiments for the Safety Analysis of
> Exoskeleton System," *Proceedings of ESREL 2020 / PSAM 15*, 2020.
> arXiv:[2101.01283](https://arxiv.org/abs/2101.01283).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
