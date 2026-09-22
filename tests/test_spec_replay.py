"""Specs: export as plain data, rebuild, replay exactly."""
import json

import pytest

from fiblock import (MISSING, Bias, Campaign, ConstantTime, Delay, Deterministic, DurationDistribution, Exponential,
                     FailureRate, FailureTimeDistribution, FaultInjector, InfiniteTime, Mixture, Never, Noise, PacketLoss,
                     TabulatedRate, Trigger, Uniform, Weibull)


def scenario(seed=42):
    a = FaultInjector(Bias(0.3), FailureTimeDistribution(Weibull(1.5, 20.0)), DurationDistribution(Exponential(0.2)), name="bias")
    b = FaultInjector(Delay(Uniform(0.5, 2.0)), Never(), ConstantTime(5.0),
                      trigger=Trigger(by="bias", delay=Exponential(1.0)), name="late")
    c = FaultInjector(PacketLoss(0.3, substitute=MISSING), FailureRate(TabulatedRate([0, 50], [0.01, 0.2])), ConstantTime(2.0), name="drop")
    d = FaultInjector(Noise(0.05, relative=True, distribution=Mixture([Uniform(-1, 1), Uniform(-3, 3)], [0.9, 0.1])),
                      Deterministic(10.0), InfiniteTime(), name="noisy")
    return Campaign({"methane_sensor": a, "bus": [b, c], "water_sensor": d}, seed=seed, name="scenario-1",
                    record_data_errors=True)


def trace(c, n=80):
    return [(c.apply("methane_sensor", 1.0, t=float(t)), c.apply("bus", float(t)), c.apply("water_sensor", 2.0))
            for t in range(n)]


def test_same_seed_replays_exactly_and_different_seed_differs():
    assert trace(scenario(42)) == trace(scenario(42))
    assert trace(scenario(42)) != trace(scenario(43))


def test_reset_replays_without_rebuilding():
    c = scenario(7)
    t1, l1 = trace(c), c.log.to_dicts()
    c.reset()
    assert trace(c) == t1 and c.log.to_dicts() == l1


def test_spec_round_trip_through_json_replays_exactly():
    c = scenario(99)
    text = c.to_json()
    spec = json.loads(text)
    assert spec["seed"] == 99 and spec["name"] == "scenario-1" and list(spec["points"]) == ["methane_sensor", "bus", "water_sensor"]
    late = spec["points"]["bus"][0]
    assert late["kind"] == "FaultInjector" and late["fault"] == {"kind": "Delay", "value": {"kind": "Uniform", "low": 0.5, "high": 2.0}, "gap": "missing"}
    assert late["event"] == {"kind": "Never"}
    assert late["trigger"] == {"kind": "Trigger", "by": ["bias"], "delay": {"kind": "Exponential", "rate": 1.0},
                               "probability": 1.0, "repeat": True}
    assert spec["points"]["bus"][1]["fault"]["substitute"] == {"kind": "MISSING"}
    c2 = Campaign.from_json(text)
    assert trace(c2) == trace(c) and c2.log.to_dicts() == c.log.to_dicts()


def test_edited_fault_value_appears_in_spec_and_changes_replay():
    c = scenario(5)
    base = trace(c)
    c.get("bias").fault.value = 0.9
    c.reset()
    assert c.spec()["points"]["methane_sensor"][0]["fault"]["value"] == 0.9
    assert trace(c) != base


def test_callable_distributions_are_reported_but_not_replayable():
    c = Campaign({"x": FaultInjector(Bias(1.0), FailureTimeDistribution(lambda rng: 1.0), InfiniteTime())}, seed=1)
    spec = c.spec()
    assert spec["points"]["x"][0]["event"]["distribution"]["kind"] == "FromCallable"
    with pytest.raises(ValueError, match="cannot rebuild"):
        Campaign.from_spec(spec)


def test_unknown_kind_gives_clear_error():
    with pytest.raises(KeyError, match="unknown kind"):
        Campaign.from_spec({"seed": 1, "points": {"x": [{"kind": "NoSuchThing"}]}})
