"""The campaign: several injectors, chaining, custom fault types, seeds."""
import numpy as np
import pytest

from fiblock import (Bias, Campaign, ConstantTime, Deterministic, FaultInjector, FaultType, Freeze, Gain, InfiniteTime,
                     Never, Noise, Once, PacketLoss, StuckAt, Trigger, register)


def test_injectors_on_one_point_apply_in_attachment_order():
    c = Campaign({"x": [FaultInjector(Bias(1.0), Deterministic(), InfiniteTime(), name="b"),
                        FaultInjector(Gain(2.0), Deterministic(), InfiniteTime(), name="s")]}, seed=1)
    o = c.inject("x", 1.0, t=0)
    assert o.value == 4.0 and o.data_error and o.caused_by == ("b", "s") and o.active == ("b", "s")
    c2 = Campaign({"x": [FaultInjector(Gain(2.0), Deterministic(), InfiniteTime()),
                         FaultInjector(Bias(1.0), Deterministic(), InfiniteTime())]}, seed=1)
    assert c2.apply("x", 1.0, t=0) == 3.0


def test_points_are_independent_and_auto_named():
    c = Campaign({"a": FaultInjector(Bias(1.0), Deterministic(1.0), InfiniteTime()),
                  "b": FaultInjector(Gain(0.5), Deterministic(2.0), InfiniteTime())}, seed=1)
    a = [c.apply("a", 1.0, t=float(t)) for t in range(3)]
    b = [c.apply("b", 1.0) for _ in range(3)]
    assert a == [1.0, 2.0, 2.0] and b == [0.5, 0.5, 0.5]
    assert c.points() == ["a", "b"] and [i.name for i in c.injectors] == ["Bias@a#0", "Gain@b#1"]


def test_missing_short_circuits_later_injectors():
    c = Campaign({"x": [FaultInjector(PacketLoss(), Deterministic(), InfiniteTime(), name="drop"),
                        FaultInjector(Bias(1.0), Deterministic(), InfiniteTime(), name="bias")]}, seed=1)
    o = c.inject("x", 1.0, t=0)
    assert o.missing and o.data_error and o.caused_by == ("drop",) and o.active == ("drop",)


def test_chained_on_activation_with_delay():
    a = FaultInjector(Bias(1.0), Deterministic(2.0), ConstantTime(10.0), name="bias")
    b = FaultInjector(PacketLoss(), Never(), ConstantTime(1.0), trigger=Trigger(by=a, delay=1.5), name="loss")
    c = Campaign({"s1": a, "s2": b}, seed=1)
    out = [c.inject("s2", 1.0, t=float(t)).missing for t in range(7)]
    assert out == [False, False, False, False, True, False, False], "loss active on [3.5, 4.5): only t=4"
    rec = c.log.filter(injector="loss", kind="activation")[0]
    assert rec.source == "trigger:bias" and rec.sampled["trigger_delay"] == 1.5 and rec.sampled["scheduled_time"] == 3.5


def test_chained_fault_with_the_same_exposure_as_its_source():
    """The paper's example: the chained fault is activated with the same duration as the first one."""
    first = FaultInjector(Freeze(), Deterministic(1.0), ConstantTime(2.0), name="position_freeze")
    second = FaultInjector(StuckAt(0.0), Never(), ConstantTime(2.0), trigger=Trigger(by="position_freeze"), name="velocity_stuck")
    c = Campaign({"position": first, "velocity": second}, seed=1)
    pos, vel = [], []
    for t in range(5):
        pos.append(c.apply("position", float(t) * 10, t=float(t)))
        vel.append(c.apply("velocity", 5.0))
    assert pos == [0.0, 0.0, 0.0, 30.0, 40.0] and vel == [5.0, 0.0, 0.0, 5.0, 5.0]
    assert [(r.injector, r.kind, r.time) for r in c.log] == [
        ("position_freeze", "activation", 1.0), ("velocity_stuck", "activation", 1.0),
        ("position_freeze", "deactivation", 3.0), ("velocity_stuck", "deactivation", 3.0)]


def test_chained_probability_uses_the_triggered_injectors_stream():
    hits = 0
    for seed in range(60):
        a = FaultInjector(Bias(1.0), Deterministic(0.0), Once(), name="a")
        b = FaultInjector(Bias(1.0), Never(), Once(), trigger=Trigger(by="a", probability=0.5), name="b")
        c = Campaign({"x": a, "y": b}, seed=seed)
        c.advance(0.0)
        hits += b.error_flag
    assert 15 < hits < 45


def test_chain_cascades_in_one_step_regardless_of_order():
    a = FaultInjector(Bias(1.0), Deterministic(0.0), InfiniteTime(), name="a")
    b = FaultInjector(Bias(1.0), Never(), InfiniteTime(), trigger=Trigger(by="a"), name="b")
    cc = FaultInjector(Bias(1.0), Never(), InfiniteTime(), trigger=Trigger(by="b"), name="c")
    c = Campaign({"z": cc, "y": b, "x": a}, seed=1)   # deliberately reversed order
    c.advance(0.0)
    assert [i.error_flag for i in (a, b, cc)] == [True, True, True]
    assert [r.injector for r in c.log] == ["a", "b", "c"]


def test_custom_user_defined_fault_type():
    @register
    class Spike(FaultType):
        """Add a spike whose height decays over the fault's own lifetime."""
        def __init__(self, value, decay=1.0):
            self.value = value
            self.decay = decay

        def apply(self, value, ctx):
            return value + self.value * np.exp(-self.decay * (ctx.elapsed or 0.0))

    c = Campaign({"x": FaultInjector(Spike(2.0), Deterministic(1.0), ConstantTime(3.0))}, seed=1)
    out = [c.apply("x", 0.0, t=float(t)) for t in range(5)]
    assert out == pytest.approx([0.0, 2.0, 2.0 * np.exp(-1), 2.0 * np.exp(-2), 0.0])
    assert c.log[0].parameters == {"value": 2.0, "decay": 1.0} and c.log[0].fault_type == "Spike"
    replay = Campaign.from_spec(c.spec())
    assert [replay.apply("x", 0.0, t=float(t)) for t in range(5)] == pytest.approx(out)


def test_seedless_campaign_gets_a_recorded_seed_and_replays():
    c = Campaign({"x": FaultInjector(Noise(1.0), Deterministic(), InfiniteTime())})
    assert c.seed is not None
    a = [c.apply("x", 0.0, t=float(t)) for t in range(3)]
    c.reset()
    assert [c.apply("x", 0.0, t=float(t)) for t in range(3)] == a


def test_streams_independent_of_campaign_membership():
    alone = Campaign({"x": FaultInjector(Noise(1.0), Deterministic(), InfiniteTime(), name="n")}, seed=4)
    a = [alone.apply("x", 0.0, t=float(t)) for t in range(3)]
    both = Campaign({"y": FaultInjector(Noise(1.0), Deterministic(), InfiniteTime(), name="other"),
                     "x": FaultInjector(Noise(1.0), Deterministic(), InfiniteTime(), name="n")}, seed=4)
    b = []
    for t in range(3):
        both.apply("y", 0.0, t=float(t))
        b.append(both.apply("x", 0.0))
    assert a == b, "adding an unrelated injector must not change another injector's draws"


def test_duplicate_names_and_double_attachment_are_rejected():
    with pytest.raises(ValueError):
        Campaign({"x": [FaultInjector(Bias(1.0), Deterministic(), InfiniteTime(), name="same"),
                        FaultInjector(Bias(2.0), Deterministic(), InfiniteTime(), name="same")]}, seed=1)
    inj = FaultInjector(Bias(1.0), Deterministic(), InfiniteTime())
    c = Campaign({"x": inj}, seed=1)
    with pytest.raises(ValueError):
        c.attach("y", inj)


def test_inject_auto_advances_and_same_time_is_idempotent():
    c = Campaign({"x": FaultInjector(Bias(1.0), Deterministic(2.0), Once())}, seed=1)
    assert c.apply("x", 0.0, t=2.0) == 1.0
    assert c.apply("x", 0.0, t=2.0) == 1.0
    assert c.apply("x", 0.0, t=3.0) == 0.0


def test_trigger_overrules_the_injectors_own_event():
    src = FaultInjector(Bias(1.0), Deterministic(1.0), Once(), name="src")
    both = FaultInjector(Bias(1.0), Deterministic(50.0), Once(), trigger=Trigger(by="src"), name="both")
    c = Campaign({"x": src, "y": both}, seed=1)
    out = [c.apply("y", 0.0, t=float(t)) for t in range(4)]
    assert out == [0.0, 1.0, 0.0, 0.0], "forced at t=1 by the trigger although its own event says t=50"
    assert c.log.filter(injector="both", kind="activation")[0].source == "trigger:src"
    for t in range(4, 52):
        c.advance(float(t))
    assert [r.time for r in c.log.filter(injector="both", kind="activation")] == [1.0, 50.0], "and its own event still fires later"
