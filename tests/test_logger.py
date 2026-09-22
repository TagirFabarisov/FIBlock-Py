"""The injection log: fault-injection records and data-error records."""
import json

from fiblock import (Bias, Campaign, DataErrorRecord, Deterministic, DurationDistribution, Exponential,
                     FailureTimeDistribution, FaultInjector, InfiniteTime, InjectionLog, InjectionRecord, Noise,
                     PacketLoss, Weibull)


def test_fault_records_carry_identity_times_parameters_samples_and_seed():
    inj = FaultInjector(Noise(0.1), FailureTimeDistribution(Exponential(1.0)), DurationDistribution(Weibull(2.0, 2.0)),
                        name="noisy")
    c = Campaign({"x": inj}, seed=77)
    for t in range(40):
        c.apply("x", 1.0, t=float(t))
    act = c.log.filter(kind="activation")[0]
    assert isinstance(act, InjectionRecord)
    assert act.injector == "noisy" and act.fault_type == "Noise" and act.point == "x"
    assert act.parameters["value"] == 0.1 and act.parameters["distribution"] == {"kind": "Normal", "mean": 0.0, "std": 1.0}
    assert set(act.sampled) >= {"activation_time", "scheduled_time", "time_to_failure", "duration"}
    assert act.seed["root_seed"] == 77 and isinstance(act.seed["name_key"], int)
    deact = c.log.filter(kind="deactivation")[0]
    assert deact.time >= act.time + act.sampled["duration"]
    assert json.loads(c.log.to_json())[0]["kind"] == "activation" and str(act).startswith("t=")


def test_data_errors_are_observed_by_the_campaign_not_recorded_by_default():
    c = Campaign({"x": FaultInjector(PacketLoss(0.5), Deterministic(), InfiniteTime(), name="drop")}, seed=3)
    outs = [c.inject("x", 1.0, t=float(t)) for t in range(40)]
    assert any(o.data_error for o in outs) and any(not o.data_error for o in outs), "the fault is active throughout, the data error only sometimes"
    assert all(o.active == ("drop",) for o in outs)
    assert all(o.caused_by == (("drop",) if o.data_error else ()) for o in outs)
    assert c.log.counts() == {"activation": 1}, "no data-error records unless asked"


def test_data_error_records_when_asked():
    c = Campaign({"x": FaultInjector(Bias(1.0), Deterministic(1.0), InfiniteTime(), name="b")}, seed=1, record_data_errors=True)
    for t in range(4):
        c.apply("x", float(t), t=float(t))
    errs = c.log.data_errors()
    assert len(errs) == 3 and all(isinstance(e, DataErrorRecord) for e in errs)
    assert errs[0].time == 1.0 and errs[0].before == 1.0 and errs[0].after == 2.0 and errs[0].caused_by == ("b",)
    assert c.log.filter(kind="data_error", injector="b") == errs and c.log.faults().counts() == {"activation": 1}
    assert str(errs[0]).startswith("t=1 data_error")


def test_a_shared_log_can_be_supplied():
    shared = InjectionLog()
    c = Campaign({"x": FaultInjector(Bias(1.0), Deterministic(), InfiniteTime())}, seed=1, log=shared)
    c.advance(0.0)
    assert shared is c.log and len(shared) == 1
