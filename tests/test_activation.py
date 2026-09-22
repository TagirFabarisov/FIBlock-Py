import math

import numpy as np
import pytest

from fiblock import (At, Bias, Campaign, Exponential, Fixed, Immediately, Never, Once, Permanent, PerStep, Rate,
                     SampledTime, TabulatedRate, When)


def values_of(outs):
    return [o.value for o in outs]


def test_at_fires_once_at_first_time_reached(drive):
    c = Campaign([Bias("x", 1.0, activation=At(2.5), duration=Permanent())], seed=1)
    outs = drive(c, "x", [0.0] * 6, times=[0, 1, 2, 3, 4, 5])
    assert values_of(outs) == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0], "bias must start at the first t >= 2.5"
    ev = c.events.filter(kind="activated")
    assert len(ev) == 1 and ev[0].time == 3.0 and ev[0].sampled["scheduled_time"] == 2.5


def test_at_does_not_refire_after_deactivation(drive):
    c = Campaign([Bias("x", 1.0, activation=At(1.0), duration=Fixed(2.0))], seed=1)
    outs = drive(c, "x", [0.0] * 8)
    assert values_of(outs) == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert c.events.counts() == {"activated": 1, "deactivated": 1}


def test_immediately_and_never(drive):
    c = Campaign([Bias("x", 1.0, activation=Immediately()), Bias("y", 1.0, activation=Never())], seed=1)
    assert drive(c, "x", [0.0])[0].value == 1.0
    assert drive(c, "y", [0.0], times=[1])[0].value == 0.0
    c.activate("Bias@y#1")
    assert c.apply("y", 0.0) == 1.0


def test_sampled_time_is_reproducible_and_seed_dependent():
    def activation_time(seed):
        c = Campaign([Bias("x", 1.0, activation=SampledTime(Exponential(0.5)))], seed=seed)
        for t in range(0, 200):
            c.advance(float(t))
            if c.events.filter(kind="activated"):
                return c.events[0].time, c.events[0].sampled["sampled_delay"]
        return None
    a = activation_time(123)
    b = activation_time(123)
    d = activation_time(124)
    assert a == b, "same seed must give the same activation time"
    assert a != d, "different seeds should (almost surely) differ"
    assert a[0] == math.ceil(a[1]) or a[0] == math.floor(a[1]) + 1 or a[0] >= a[1]


def test_sampled_time_repeat_cycles(drive):
    c = Campaign([Bias("x", 1.0, activation=SampledTime(1.0, repeat=True), duration=Fixed(1.0))], seed=3)
    outs = drive(c, "x", [0.0] * 8)
    # activates at t>=1 (constant delay 1), lasts 1, re-arms 1 after deactivation, ...
    assert values_of(outs) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_rate_activation_is_step_size_independent_in_expectation():
    n_runs, horizon, lam = 400, 20.0, 0.1
    def count(dt, seed):
        c = Campaign([Bias("x", 1.0, activation=Rate(lam, repeat=False))], seed=seed)
        t = 0.0
        while t <= horizon:
            c.advance(t); t += dt
        return len(c.events.filter(kind="activated"))
    coarse = sum(count(1.0, s) for s in range(n_runs)) / n_runs
    fine = sum(count(0.1, s) for s in range(n_runs)) / n_runs
    expected = 1 - math.exp(-lam * horizon)
    assert abs(coarse - expected) < 0.08 and abs(fine - expected) < 0.08


def test_rate_with_tabulated_curve_and_callable():
    c = Campaign([Bias("x", 1.0, activation=Rate(TabulatedRate([0, 10], [0.0, 0.0]))),
                  Bias("y", 1.0, activation=Rate(lambda t: 0.0))], seed=1)
    for t in range(0, 50):
        c.advance(float(t))
    assert not c.events, "zero rate must never activate"


def test_per_step_probability_one_fires_on_second_advance():
    c = Campaign([Bias("x", 1.0, activation=PerStep(1.0), duration=Once())], seed=1)
    c.advance(0.0)
    assert c.active() and c.events[0].time == 0.0


def test_when_condition_edge_triggered():
    c = Campaign([Bias("x", 1.0, activation=When(lambda ctx: ctx.host["level"] > 5), duration=Once())], seed=1)
    for t, level in enumerate([1, 6, 7, 8, 2, 9]):
        c.advance(float(t), host={"level": level})
    times = [e.time for e in c.events.filter(kind="activated")]
    assert times == [1.0, 5.0], "edge-triggered: only the false->true transitions"


def test_when_condition_level_triggered():
    c = Campaign([Bias("x", 1.0, activation=When(lambda ctx: ctx.host > 5, edge=False), duration=Once())], seed=1)
    for t, level in enumerate([1, 6, 7, 8, 2, 9]):
        c.advance(float(t), host=level)
    times = [e.time for e in c.events.filter(kind="activated")]
    assert times == [1.0, 2.0, 3.0, 5.0], "level: re-activates at every step the condition holds (Once frees it each step)"


def test_max_activations_limits_repeats():
    c = Campaign([Bias("x", 1.0, activation=PerStep(1.0), duration=Once(), max_activations=2)], seed=1)
    for t in range(10):
        c.advance(float(t))
    assert len(c.events.filter(kind="activated")) == 2


def test_disabled_fault_never_activates_by_itself():
    c = Campaign([Bias("x", 1.0, activation=Immediately(), enabled=False)], seed=1)
    c.advance(0.0)
    assert not c.events and c.apply("x", 0.0) == 0.0


def test_time_must_not_go_backwards():
    c = Campaign([Bias("x", 1.0)], seed=1)
    c.advance(5.0)
    with pytest.raises(ValueError):
        c.advance(4.0)
    with pytest.raises(ValueError):
        c.inject("x", 0.0, t=4.0)
