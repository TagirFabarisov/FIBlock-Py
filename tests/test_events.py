"""Fault events: when a fault activates."""
import math

import pytest

from fiblock import (Bias, Campaign, ConstantTime, Deterministic, Exponential, FailureProbability,
                     FailureRate, FailureTimeDistribution, FaultInjector, InfiniteTime, MeanTimeToFailure, Never, Once,
                     TabulatedRate)
from conftest import drive, single, values


def test_deterministic_fires_once_at_first_time_reached():
    c = single(Bias(1.0), Deterministic(2.5), InfiniteTime())
    out = [o.value for o in drive(c, "x", [0.0] * 6)]
    assert out == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0], "bias must start at the first t >= 2.5"
    rec = c.log.filter(kind="activation")
    assert len(rec) == 1 and rec[0].time == 3.0 and rec[0].sampled["scheduled_time"] == 2.5


def test_deterministic_does_not_refire_after_deactivation():
    c = single(Bias(1.0), Deterministic(1.0), ConstantTime(2.0))
    assert values(c, "x", 8) == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert c.log.counts() == {"activation": 1, "deactivation": 1}


def test_deterministic_default_is_immediate_and_never_needs_manual_activation():
    c = Campaign({"x": FaultInjector(Bias(1.0), Deterministic(), InfiniteTime(), name="now"),
                  "y": FaultInjector(Bias(1.0), Never(), InfiniteTime(), name="never")}, seed=1)
    assert c.apply("x", 0.0, t=0) == 1.0
    assert c.apply("y", 0.0, t=1) == 0.0
    c.activate("never")
    assert c.apply("y", 0.0) == 1.0 and c.log.filter(injector="never")[0].source == "manual"


def test_failure_time_distribution_is_reproducible_and_seed_dependent():
    def first_activation(seed):
        c = single(Bias(1.0), FailureTimeDistribution(Exponential(0.5)), InfiniteTime(), seed=seed)
        for t in range(200):
            c.advance(float(t))
            if c.log:
                return c.log[0].time, c.log[0].sampled["time_to_failure"]
    a, b, d = first_activation(123), first_activation(123), first_activation(124)
    assert a == b and a != d
    assert a[0] >= a[1], "activation happens at the first step at or after the sampled time"


def test_mean_time_to_failure_repeat_cycles_from_deactivation():
    c = single(Bias(1.0), MeanTimeToFailure(1.0, spread=0.0), ConstantTime(1.0))
    assert values(c, "x", 8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_mean_time_to_failure_default_is_exponential_with_that_mean():
    samples = []
    for seed in range(300):
        c = single(Bias(1.0), MeanTimeToFailure(10.0, repeat=False), InfiniteTime(), seed=seed)
        samples.append(c.injectors[0].event._sample)
    assert abs(sum(samples) / len(samples) - 10.0) < 1.5


def test_failure_rate_is_step_size_independent_in_expectation():
    n, horizon, lam = 400, 20.0, 0.1
    def count(dt, seed):
        c = single(Bias(1.0), FailureRate(lam, repeat=False), InfiniteTime(), seed=seed)
        t = 0.0
        while t <= horizon:
            c.advance(t)
            t += dt
        return len(c.log.filter(kind="activation"))
    coarse = sum(count(1.0, s) for s in range(n)) / n
    fine = sum(count(0.1, s) for s in range(n)) / n
    expected = 1 - math.exp(-lam * horizon)
    assert abs(coarse - expected) < 0.08 and abs(fine - expected) < 0.08


def test_failure_rate_tabulated_and_callable_zero_never_fires():
    c = Campaign({"x": FaultInjector(Bias(1.0), FailureRate(TabulatedRate([0, 10], [0.0, 0.0])), InfiniteTime()),
                  "y": FaultInjector(Bias(1.0), FailureRate(lambda t: 0.0), InfiniteTime())}, seed=1)
    for t in range(50):
        c.advance(float(t))
    assert not c.log


def test_failure_probability_one_fires_on_first_step():
    c = single(Bias(1.0), FailureProbability(1.0), Once())
    c.advance(0.0)
    assert c.active() and c.log[0].time == 0.0



def test_max_activations_and_enabled():
    c = single(Bias(1.0), FailureProbability(1.0), Once(), max_activations=2)
    for t in range(10):
        c.advance(float(t))
    assert len(c.log.filter(kind="activation")) == 2
    d = single(Bias(1.0), Deterministic(), InfiniteTime(), enabled=False)
    d.advance(0.0)
    assert not d.log and d.apply("x", 0.0) == 0.0


def test_time_must_not_go_backwards():
    c = single(Bias(1.0), Deterministic(), InfiniteTime())
    c.advance(5.0)
    with pytest.raises(ValueError):
        c.advance(4.0)
    with pytest.raises(ValueError):
        c.inject("x", 0.0, t=4.0)
