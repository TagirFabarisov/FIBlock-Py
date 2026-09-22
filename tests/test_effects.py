"""Fault effects: how long a fault stays active."""
from fiblock import (Bias, ConstantTime, Deterministic, DurationDistribution, InfiniteTime, MeanTimeToRepair, Once,
                     Uniform)
from conftest import single, values


def test_once_lasts_one_step():
    c = single(Bias(1.0), Deterministic(1.0), Once())
    assert values(c, "x", 5) == [0.0, 1.0, 0.0, 0.0, 0.0]
    assert [r.time for r in c.log] == [1.0, 2.0]


def test_constant_time_ends_at_the_step_reaching_the_end():
    c = single(Bias(1.0), Deterministic(1.0), ConstantTime(2.0))
    assert values(c, "x", 6) == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0], "active on [1, 3)"
    assert c.log.filter(kind="deactivation")[0].time == 3.0


def test_infinite_time_until_explicit_deactivation():
    c = single(Bias(1.0), Deterministic(), InfiniteTime(), name="b")
    assert values(c, "x", 3) == [1.0, 1.0, 1.0]
    c.deactivate("b")
    assert c.apply("x", 0.0, t=3.0) == 0.0
    rec = c.log.filter(kind="deactivation")
    assert len(rec) == 1 and rec[0].source == "manual"


def test_duration_distribution_recorded_and_reproducible():
    def run(seed):
        c = single(Bias(1.0), Deterministic(0.0), DurationDistribution(Uniform(1.0, 5.0)), seed=seed)
        return values(c, "x", 10), c.log[0].sampled["duration"]
    (v1, d1), (v2, d2) = run(9), run(9)
    assert v1 == v2 and d1 == d2 and 1.0 <= d1 <= 5.0
    assert sum(v1) == len([t for t in range(10) if t < d1]), "active exactly while t < duration"


def test_mean_time_to_repair_exponential_default_and_normal_spread():
    means = []
    for seed in range(300):
        c = single(Bias(1.0), Deterministic(0.0), MeanTimeToRepair(4.0), seed=seed)
        c.advance(0.0)
        means.append(c.log[0].sampled["duration"])
    assert abs(sum(means) / len(means) - 4.0) < 0.6
    c = single(Bias(1.0), Deterministic(0.0), MeanTimeToRepair(4.0, spread=0.0))
    assert values(c, "x", 6) == [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]



def test_explicit_activate_and_deactivate_with_time():
    c = single(Bias(1.0), Deterministic(100.0), InfiniteTime(), name="b")
    c.activate("b", t=2.0)
    assert c.apply("x", 0.0) == 1.0
    c.deactivate("b", t=4.0)
    assert c.apply("x", 0.0) == 0.0
    assert [(r.kind, r.time, r.source) for r in c.log] == [("activation", 2.0, "manual"), ("deactivation", 4.0, "manual")]
