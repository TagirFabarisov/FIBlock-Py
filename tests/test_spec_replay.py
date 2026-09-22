import json

import pytest

from fiblock import (MISSING, At, Bias, Campaign, Delay, Exponential, Fixed, Mixture, Noise, PacketLoss, Rate,
                     SampledDuration, SampledTime, TabulatedRate, Triggered, Uniform, Until, Weibull, When)


def scenario(seed=42):
    a = Bias("methane_sensor", 0.3, activation=SampledTime(Weibull(1.5, 20.0)), duration=SampledDuration(Exponential(0.2)), name="bias")
    b = Delay("bus", delay=Uniform(0.5, 2.0), activation=Triggered(by="bias", on="activated", delay=Exponential(1.0)),
              duration=Fixed(5.0), name="late")
    c = PacketLoss("bus", probability=0.3, activation=Rate(TabulatedRate([0, 50], [0.01, 0.2])), duration=Fixed(2.0),
                   substitute=MISSING, name="drop")
    d = Noise("water_sensor", 0.05, relative=True, distribution=Mixture([Uniform(-1, 1), Uniform(-3, 3)], [0.9, 0.1]),
              activation=At(10.0), name="noisy")
    return Campaign([a, b, c, d], seed=seed, name="scenario-1", record_manifestations=True)


def trace(c, n=80):
    out = []
    for t in range(n):
        out.append((c.apply("methane_sensor", 1.0, t=float(t)), c.apply("bus", float(t)), c.apply("water_sensor", 2.0)))
    return out


def test_same_seed_replays_exactly_and_different_seed_differs():
    t1 = trace(scenario(42))
    t2 = trace(scenario(42))
    t3 = trace(scenario(43))
    assert t1 == t2
    assert t1 != t3


def test_reset_replays_without_rebuilding():
    c = scenario(7)
    t1, e1 = trace(c), c.events.to_dicts()
    c.reset()
    t2, e2 = trace(c), c.events.to_dicts()
    assert t1 == t2 and e1 == e2


def test_spec_round_trip_through_json_replays_exactly():
    c = scenario(99)
    text = c.to_json()
    spec = json.loads(text)
    assert spec["seed"] == 99 and spec["name"] == "scenario-1" and len(spec["faults"]) == 4
    assert spec["faults"][1]["activation"] == {"kind": "Triggered", "by": ["bias"], "on": "activated",
                                               "delay": {"kind": "Exponential", "rate": 1.0}, "probability": 1.0, "repeat": True}
    assert spec["faults"][2]["parameters"]["substitute"] == {"kind": "MISSING"}
    c2 = Campaign.from_json(text)
    assert trace(c2) == trace(c)
    assert c2.events.to_dicts() == c.events.to_dicts()


def test_edited_parameter_appears_in_spec_and_changes_replay():
    c = scenario(5)
    base = trace(c)
    c.get("bias").magnitude = 0.9
    c.reset()
    assert c.spec()["faults"][0]["parameters"]["magnitude"] == 0.9
    assert trace(c) != base


def test_callable_conditions_are_not_replayable_from_spec_but_are_reported():
    c = Campaign([Bias("x", 1.0, activation=When(lambda ctx: True), duration=Until(lambda ctx: False))], seed=1)
    spec = c.spec()
    assert spec["faults"][0]["activation"]["condition"]["kind"] == "Callable"
    with pytest.raises(ValueError, match="cannot rebuild"):
        Campaign.from_spec(spec)


def test_unknown_kind_gives_clear_error():
    with pytest.raises(KeyError, match="unknown kind"):
        Campaign.from_spec({"seed": 1, "faults": [{"kind": "NoSuchFault", "target": "x", "parameters": {}}]})
