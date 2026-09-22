"""The fault injector used on its own, without a campaign."""
import pytest

from fiblock import Bias, ConstantTime, Deterministic, FailureRate, FaultInjector, InjectionLog, Noise, Once


def test_standalone_injector_needs_a_seed():
    inj = FaultInjector(Bias(1.0), Deterministic(1.0), Once())
    with pytest.raises(ValueError, match="no random stream"):
        inj.step(0.0)


def test_standalone_injector_runs_and_records_to_its_recorder():
    log = InjectionLog()
    inj = FaultInjector(Bias(1.0), Deterministic(1.0), ConstantTime(2.0), seed=5, recorder=log, name="b")
    out = []
    for t in range(5):
        inj.step(float(t))
        out.append(inj.inject(0.0).value)
    assert out == [0.0, 1.0, 1.0, 0.0, 0.0]
    assert inj.injection_points == [1.0] and inj.activation_count == 1
    assert [r.kind for r in log] == ["activation", "deactivation"] and log[0].point is None


def test_standalone_noise_is_reproducible_by_seed():
    def run(seed):
        inj = FaultInjector(Noise(1.0), Deterministic(), ConstantTime(10.0), seed=seed)
        vals = []
        for t in range(4):
            inj.step(float(t))
            vals.append(inj.inject(0.0).value)
        return vals
    assert run(1) == run(1) and run(1) != run(2)


def test_step_returns_records_and_error_flag_reflects_state():
    inj = FaultInjector(Bias(1.0), FailureRate(1e9), Once(), seed=1)
    assert inj.step(0.0) == [] and not inj.error_flag          # dt = 0 on the first step
    recs = inj.step(1.0)
    assert [r.kind for r in recs] == ["activation"] and inj.error_flag
    recs = inj.step(2.0)
    assert [r.kind for r in recs] == ["deactivation", "activation"], "expiry then re-activation in one step"
