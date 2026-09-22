import json

import numpy as np
import pytest

from fiblock import (MISSING, At, Bias, Campaign, Delay, Exponential, Fault, Fixed, Immediately, Noise, Normal, Once,
                     PacketLoss, Permanent, Rate, SampledDuration, SampledTime, Scale, Triggered, Weibull, register)


def test_multiple_faults_same_target_apply_in_order():
    c = Campaign([Bias("x", 1.0), Scale("x", 2.0)], seed=1)
    o = c.inject("x", 1.0, t=0)
    assert o.value == 4.0 and o.manifested == ("Bias@x#0", "Scale@x#1")
    c2 = Campaign([Scale("x", 2.0), Bias("x", 1.0)], seed=1)
    assert c2.apply("x", 1.0, t=0) == 3.0


def test_multiple_faults_different_targets_are_independent():
    c = Campaign([Bias("a", 1.0, activation=At(1.0)), Scale("b", 0.5, activation=At(2.0))], seed=1)
    a = [c.apply("a", 1.0, t=float(t)) for t in range(3)]
    b = [c.apply("b", 1.0) for _ in range(3)]
    assert a == [1.0, 2.0, 2.0] and b == [0.5, 0.5, 0.5]
    assert sorted(c.targets()) == ["a", "b"]


def test_missing_short_circuits_later_faults():
    c = Campaign([PacketLoss("x"), Bias("x", 1.0)], seed=1)
    o = c.inject("x", 1.0, t=0)
    assert o.missing and o.manifested == ("PacketLoss@x#0",) and o.applied == ("PacketLoss@x#0",)


def test_chained_on_activation_with_delay():
    a = Bias("s1", 1.0, activation=At(2.0), duration=Fixed(10.0), name="bias")
    b = PacketLoss("s2", activation=Triggered(by=a, on="activated", delay=1.5), duration=Fixed(1.0), name="loss")
    c = Campaign([a, b], seed=1)
    out = [c.inject("s2", 1.0, t=float(t)).missing for t in range(7)]
    assert out == [False, False, False, False, True, False, False], "loss active on [3.5, 4.5): only t=4"
    ev = c.events.filter(fault="loss", kind="activated")[0]
    assert ev.source == "trigger:bias" and ev.sampled["trigger_delay"] == 1.5 and ev.sampled["scheduled_time"] == 3.5


def test_chained_on_manifestation_and_on_deactivation():
    a = PacketLoss("link", probability=1.0, activation=At(1.0), duration=Fixed(2.0), name="drop")
    b = Bias("ctrl", 1.0, activation=Triggered(by="drop", on="manifested"), duration=Once(), name="glitch")
    d = Scale("pump", 0.0, activation=Triggered(by="drop", on="deactivated"), duration=Fixed(1.0), name="stall")
    c = Campaign([a, b, d], seed=1)
    ctrl, pump = [], []
    for t in range(6):
        c.inject("link", 1.0, t=float(t))
        ctrl.append(c.apply("ctrl", 0.0))
        pump.append(c.apply("pump", 1.0))
    assert ctrl == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0], "glitch active during the steps in which a packet was dropped"
    assert pump == [1.0, 1.0, 1.0, 0.0, 1.0, 1.0], "stall starts when the drop ends (t=3)"


def test_chained_probability_uses_the_triggered_faults_stream():
    hits = 0
    for seed in range(60):
        a = Bias("x", 1.0, activation=At(0.0), duration=Once(), name="a")
        b = Bias("y", 1.0, activation=Triggered(by="a", probability=0.5), duration=Once(), name="b")
        c = Campaign([a, b], seed=seed)
        c.advance(0.0)
        hits += b.active
    assert 15 < hits < 45


def test_trigger_cascade_in_same_step_and_no_self_trigger():
    a = Bias("x", 1.0, activation=At(0.0), name="a")
    b = Bias("y", 1.0, activation=Triggered(by="a"), name="b")
    cc = Bias("z", 1.0, activation=Triggered(by="b"), name="c")
    c = Campaign([cc, b, a], seed=1)    # deliberately reversed order
    c.advance(0.0)
    assert [f.active for f in (a, b, cc)] == [True, True, True]
    assert [e.fault for e in c.events] == ["a", "b", "c"]


def test_custom_user_defined_fault():
    @register
    class Spike(Fault):
        """Add a spike whose height decays over the fault's own lifetime."""
        def __init__(self, target, height, decay=1.0, **kw):
            super().__init__(target, **kw)
            self.height = height
            self.decay = decay

        def apply(self, value, ctx):
            return value + self.height * np.exp(-self.decay * (ctx.elapsed or 0.0))

    c = Campaign([Spike("x", height=2.0, activation=At(1.0), duration=Fixed(3.0))], seed=1)
    out = [c.apply("x", 0.0, t=float(t)) for t in range(5)]
    assert out == pytest.approx([0.0, 2.0, 2.0 * np.exp(-1), 2.0 * np.exp(-2), 0.0])
    assert c.events[0].parameters == {"height": 2.0, "decay": 1.0} and c.events[0].fault_type == "Spike"
    replay = Campaign.from_spec(c.spec())
    assert [replay.apply("x", 0.0, t=float(t)) for t in range(5)] == pytest.approx(out)


def test_events_carry_identity_times_parameters_samples_and_seed():
    c = Campaign([Noise("x", 0.1, activation=SampledTime(Exponential(1.0)), duration=SampledDuration(Weibull(2.0, 2.0)))],
                 seed=77, record_manifestations=True)
    for t in range(40):
        c.apply("x", 1.0, t=float(t))
    act = c.events.filter(kind="activated")[0]
    assert act.fault == "Noise@x#0" and act.fault_type == "Noise" and act.target == "x"
    assert act.parameters["amplitude"] == 0.1 and act.parameters["distribution"] == {"kind": "Normal", "mean": 0.0, "std": 1.0}
    assert set(act.sampled) >= {"activation_time", "scheduled_time", "sampled_delay", "duration"}
    assert act.seed["campaign_seed"] == 77 and isinstance(act.seed["name_key"], int)
    deact = c.events.filter(kind="deactivated")[0]
    assert deact.time >= act.time + act.sampled["duration"]
    man = c.events.filter(kind="manifested")
    assert man and all(a.time <= m.time < deact.time for m in man for a in [act])
    assert json.loads(c.events.to_json())[0]["kind"] == "activated"


def test_manifestations_counted_even_when_not_recorded():
    c = Campaign([Bias("x", 1.0)], seed=1)
    for t in range(3):
        c.apply("x", 0.0, t=float(t))
    assert c.faults[0].manifestations == 3 and not c.events.filter(kind="manifested")


def test_seedless_campaign_gets_a_recorded_seed_and_replays():
    c = Campaign([Noise("x", 1.0)])
    assert c.seed is not None
    a = [c.apply("x", 0.0, t=float(t)) for t in range(3)]
    c.reset()
    assert [c.apply("x", 0.0, t=float(t)) for t in range(3)] == a


def test_fault_streams_independent_of_campaign_membership():
    """Adding an unrelated fault must not change another fault's random draws."""
    n = Noise("x", 1.0, name="n")
    alone = Campaign([n], seed=4)
    a = [alone.apply("x", 0.0, t=float(t)) for t in range(3)]
    n2 = Noise("x", 1.0, name="n")
    other = Noise("y", 1.0, name="other")
    b = []
    c = Campaign([other, n2], seed=4)
    for t in range(3):
        c.apply("y", 0.0, t=float(t))
        b.append(c.apply("x", 0.0))
    assert a == b


def test_fault_cannot_belong_to_two_campaigns_and_names_unique():
    f = Bias("x", 1.0)
    Campaign([f], seed=1)
    with pytest.raises(ValueError):
        Campaign([f], seed=1)
    with pytest.raises(ValueError):
        Campaign([Bias("x", 1.0, name="same"), Bias("x", 2.0, name="same")], seed=1)


def test_inject_auto_advances_and_advance_is_idempotent_at_same_time():
    c = Campaign([Bias("x", 1.0, activation=At(2.0), duration=Once())], seed=1)
    assert c.apply("x", 0.0, t=2.0) == 1.0
    assert c.apply("x", 0.0, t=2.0) == 1.0, "same time: no new advance, still active"
    assert c.apply("x", 0.0, t=3.0) == 0.0
