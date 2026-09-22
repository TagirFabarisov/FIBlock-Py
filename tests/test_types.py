"""Fault types: what the error looks like."""
import numpy as np
import pytest

from fiblock import (MISSING, Bias, BitFlip, Campaign, ConstantTime, Delay, Deterministic, Drift, FaultInjector, Freeze,
                     Gain, InfiniteTime, Noise, PacketLoss, StuckAt, Uniform)
from conftest import single


def now(fault, **kw):
    return FaultInjector(fault, Deterministic(), InfiniteTime(), **kw)


def test_bias_absolute_relative_and_arrays():
    c = Campaign({"a": now(Bias(0.5)), "b": now(Bias(0.5, relative=True))}, seed=1)
    assert c.apply("a", 2.0, t=0) == 2.5 and c.apply("b", 2.0) == 3.0
    assert np.allclose(c.apply("a", np.array([1.0, 2.0])), [1.5, 2.5])


def test_drift_grows_with_time_since_activation():
    c = single(Drift(0.1), Deterministic(2.0), InfiniteTime())
    assert [c.apply("x", 1.0, t=float(t)) for t in range(6)] == pytest.approx([1.0, 1.0, 1.0, 1.1, 1.2, 1.3])


def test_noise_is_seeded_and_reproducible():
    def run(seed):
        c = single(Noise(0.1), Deterministic(), InfiniteTime(), seed=seed)
        return [c.apply("x", 1.0, t=float(t)) for t in range(5)]
    a, b, d = run(1), run(1), run(2)
    assert a == b and a != d and all(v != 1.0 for v in a)


def test_noise_relative_uniform_like_original_fiblock():
    c = single(Noise(0.3, relative=True, distribution=Uniform(-1, 1)), Deterministic(), InfiniteTime())
    assert all(7.0 <= c.apply("x", 10.0, t=float(t)) <= 13.0 for t in range(200))


def test_gain_and_stuck_at():
    c = Campaign({"p": now(Gain(0.6)), "q": now(StuckAt(0.0))}, seed=1)
    assert c.apply("p", 10.0, t=0) == 6.0 and c.apply("q", 10.0) == 0.0


def test_freeze_holds_last_correct_value():
    c = single(Freeze(), Deterministic(3.0), ConstantTime(2.0))
    out = [c.apply("x", float(t) * 10, t=float(t)) for t in range(7)]
    assert out == [0.0, 10.0, 20.0, 20.0, 20.0, 50.0, 60.0]
    assert c.log[0].sampled["frozen_value"] == 20.0


def test_freeze_without_prior_observation_passes_value_through():
    c = single(Freeze(), Deterministic(), InfiniteTime(), name="f")
    o = c.inject("x", 7.0, t=0)
    assert o.value == 7.0 and o.data_error is False and o.active == ("f",)


def test_packet_loss_all_probabilistic_and_substitute():
    c = Campaign({"a": now(PacketLoss()), "b": now(PacketLoss(0.5)), "c": now(PacketLoss(substitute=-1))}, seed=2)
    assert c.inject("a", 1.0, t=0).missing
    drops = sum(c.inject("b", 1.0).missing for _ in range(400))
    assert 150 < drops < 250
    assert c.apply("c", 1.0) == -1


def test_delay_onset_gap_late_delivery_and_recovery():
    c = single(Delay(2.0), Deterministic(2.0), ConstantTime(5.0))
    out = [c.apply("x", float(t), t=float(t)) for t in range(10)]
    assert out == [0.0, 1.0, MISSING, MISSING, 2.0, 3.0, 4.0, 7.0, 8.0, 9.0]


def test_delay_gap_hold_and_sampled_delay():
    c = single(Delay(2.0, gap="hold"), Deterministic(2.0), ConstantTime(5.0))
    assert [c.apply("x", float(t), t=float(t)) for t in range(8)] == [0.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 7.0]
    d = single(Delay(Uniform(1.0, 3.0)), Deterministic(0.0), InfiniteTime())
    d.advance(0.0)
    assert 1.0 <= d.log[0].sampled["delay"] <= 3.0


def test_bitflip_float_int_bool_array_and_reproducible():
    c = Campaign({"f": now(BitFlip()), "i": now(BitFlip(width=8)), "b": now(BitFlip()), "v": now(BitFlip())}, seed=11)
    f = c.apply("f", 1.0, t=0)
    assert isinstance(f, float) and f != 1.0
    i = c.apply("i", 5)
    assert isinstance(i, int) and i != 5 and -128 <= i < 128
    assert c.apply("b", True) is False
    v = c.apply("v", np.array([1.0, 2.0, 3.0]))
    assert v.shape == (3,) and int(np.sum(v != np.array([1.0, 2.0, 3.0]))) == 1
    a = single(BitFlip(2), Deterministic(), InfiniteTime(), seed=3).apply("x", 2.5, t=0)
    b = single(BitFlip(2), Deterministic(), InfiniteTime(), seed=3).apply("x", 2.5, t=0)
    assert a == b


def test_fault_value_is_a_plain_editable_attribute():
    f = Bias(0.1)
    assert f.parameters() == {"value": 0.1, "relative": False}
    c = single(f, Deterministic(), InfiniteTime())
    assert c.apply("x", 0.0, t=0) == pytest.approx(0.1)
    f.value = 0.7                                   # an external search algorithm sets a candidate
    assert c.apply("x", 0.0) == pytest.approx(0.7)
    assert c.log[0].parameters == {"value": 0.1, "relative": False}, "records keep the value at activation time"
