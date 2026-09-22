import numpy as np
import pytest

from fiblock import (MISSING, At, Bias, BitFlip, Campaign, Constant, Delay, Drift, Fixed, Freeze, Immediately, Noise,
                     Normal, PacketLoss, Permanent, Scale, StuckAt, Uniform)


def always(fault):
    """Campaign with one fault active from the first step."""
    return Campaign([fault], seed=5)


def test_bias_absolute_and_relative():
    c = Campaign([Bias("a", 0.5), Bias("b", 0.5, relative=True)], seed=1)
    assert c.apply("a", 2.0, t=0) == 2.5
    assert c.apply("b", 2.0) == 3.0
    assert np.allclose(c.apply("a", np.array([1.0, 2.0])), [1.5, 2.5])


def test_drift_grows_with_time_since_activation():
    c = always(Drift("x", rate=0.1, activation=At(2.0)))
    out = [c.apply("x", 1.0, t=float(t)) for t in range(6)]
    assert out == pytest.approx([1.0, 1.0, 1.0, 1.1, 1.2, 1.3])


def test_noise_is_seeded_and_reproducible():
    def run(seed):
        c = Campaign([Noise("x", amplitude=0.1)], seed=seed)
        return [c.apply("x", 1.0, t=float(t)) for t in range(5)]
    a, b, d = run(1), run(1), run(2)
    assert a == b and a != d
    assert all(v != 1.0 for v in a)


def test_noise_relative_uniform_like_original_fiblock():
    c = always(Noise("x", amplitude=0.3, relative=True, distribution=Uniform(-1, 1)))
    out = [c.apply("x", 10.0, t=float(t)) for t in range(200)]
    assert all(7.0 <= v <= 13.0 for v in out), "within +-30 % of the correct value"


def test_scale_and_stuck_at():
    c = Campaign([Scale("p", 0.6), StuckAt("q", 0.0)], seed=1)
    assert c.apply("p", 10.0, t=0) == 6.0
    assert c.apply("q", 10.0) == 0.0


def test_freeze_holds_last_correct_value():
    c = always(Freeze("x", activation=At(3.0), duration=Fixed(2.0)))
    out = [c.apply("x", float(t) * 10, t=float(t)) for t in range(7)]
    assert out == [0.0, 10.0, 20.0, 20.0, 20.0, 50.0, 60.0]
    assert c.events[0].sampled["frozen_value"] == 20.0


def test_freeze_without_prior_observation_passes_value_through():
    c = always(Freeze("x", activation=Immediately()))
    o = c.inject("x", 7.0, t=0)
    assert o.value == 7.0 and o.manifested == () and o.applied == ("Freeze@x#0",)


def test_packet_loss_all_and_probabilistic_and_substitute():
    c = Campaign([PacketLoss("a"), PacketLoss("b", probability=0.5), PacketLoss("c", substitute=-1)], seed=2)
    assert c.inject("a", 1.0, t=0).missing
    drops = sum(c.inject("b", 1.0).missing for _ in range(400))
    assert 150 < drops < 250
    assert c.apply("c", 1.0) == -1


def test_delay_onset_gap_then_late_delivery_then_recovery():
    c = always(Delay("x", delay=2.0, activation=At(2.0), duration=Fixed(5.0)))
    out = [c.apply("x", float(t), t=float(t)) for t in range(10)]
    # active on [2,7): values sent at 2,3,4,... arrive at 4,5,6,...; gap at 2,3; on time again from 7
    assert out == [0.0, 1.0, MISSING, MISSING, 2.0, 3.0, 4.0, 7.0, 8.0, 9.0]


def test_delay_gap_hold_keeps_last_pre_fault_value():
    c = always(Delay("x", delay=2.0, gap="hold", activation=At(2.0), duration=Fixed(5.0)))
    out = [c.apply("x", float(t), t=float(t)) for t in range(8)]
    assert out == [0.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 7.0]


def test_delay_sampled_per_activation_is_recorded():
    c = always(Delay("x", delay=Uniform(1.0, 3.0), activation=At(0.0)))
    c.advance(0.0)
    d = c.events[0].sampled["delay"]
    assert 1.0 <= d <= 3.0


def test_bitflip_float_int_bool_and_array():
    c = Campaign([BitFlip("f"), BitFlip("i", width=8), BitFlip("b"), BitFlip("v")], seed=11)
    f = c.apply("f", 1.0, t=0)
    assert isinstance(f, float) and f != 1.0
    i = c.apply("i", 5)
    assert isinstance(i, int) and i != 5 and -128 <= i < 128
    assert c.apply("b", True) is False
    v = c.apply("v", np.array([1.0, 2.0, 3.0]))
    assert v.shape == (3,) and int(np.sum(v != np.array([1.0, 2.0, 3.0]))) == 1


def test_bitflip_reproducible():
    a = Campaign([BitFlip("f", bits=2)], seed=3).apply("f", 2.5, t=0)
    b = Campaign([BitFlip("f", bits=2)], seed=3).apply("f", 2.5, t=0)
    assert a == b


def test_parameters_are_plain_editable_attributes():
    f = Bias("x", 0.1)
    assert f.parameters() == {"magnitude": 0.1, "relative": False}
    c = Campaign([f], seed=1)
    assert c.apply("x", 0.0, t=0) == pytest.approx(0.1)
    f.magnitude = 0.7            # an external search algorithm sets a candidate
    assert c.apply("x", 0.0) == pytest.approx(0.7)
    assert c.events[0].parameters == {"magnitude": 0.1, "relative": False}, "events keep the value at activation time"
