from fiblock import At, Bias, Campaign, Constant, Fixed, Immediately, Once, Permanent, SampledDuration, Uniform, Until


def vals(c, n):
    return [c.apply("x", 0.0, t=float(t)) for t in range(n)]


def test_once_lasts_one_step():
    c = Campaign([Bias("x", 1.0, activation=At(1.0), duration=Once())], seed=1)
    assert vals(c, 5) == [0.0, 1.0, 0.0, 0.0, 0.0]
    assert [e.time for e in c.events] == [1.0, 2.0]


def test_fixed_duration_end_is_inclusive_of_expiry_step():
    c = Campaign([Bias("x", 1.0, activation=At(1.0), duration=Fixed(2.0))], seed=1)
    assert vals(c, 6) == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0], "active on [1, 3), expired at the advance to t=3"
    assert c.events.filter(kind="deactivated")[0].time == 3.0


def test_permanent_until_explicit_deactivation():
    c = Campaign([Bias("x", 1.0, activation=Immediately(), duration=Permanent())], seed=1)
    assert vals(c, 3) == [1.0, 1.0, 1.0]
    c.deactivate("Bias@x#0")
    assert c.apply("x", 0.0, t=3.0) == 0.0
    ev = c.events.filter(kind="deactivated")
    assert len(ev) == 1 and ev[0].source == "manual"


def test_sampled_duration_is_recorded_and_reproducible():
    def run(seed):
        c = Campaign([Bias("x", 1.0, activation=At(0.0), duration=SampledDuration(Uniform(1.0, 5.0)))], seed=seed)
        v = vals(c, 10)
        return v, c.events[0].sampled["duration"]
    v1, d1 = run(9)
    v2, d2 = run(9)
    assert v1 == v2 and d1 == d2
    assert 1.0 <= d1 <= 5.0
    assert sum(v1) == len([t for t in range(10) if t < d1]), "active exactly while t < duration"


def test_until_condition_deactivates():
    c = Campaign([Bias("x", 1.0, activation=Immediately(), duration=Until(lambda ctx: ctx.host >= 3))], seed=1)
    out = [c.apply("x", 0.0, t=float(t), host=t) for t in range(6)]
    assert out == [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]


def test_explicit_activate_and_deactivate_with_time():
    c = Campaign([Bias("x", 1.0, activation=At(100.0))], seed=1)
    c.activate("Bias@x#0", t=2.0)
    assert c.apply("x", 0.0) == 1.0
    c.deactivate("Bias@x#0", t=4.0)
    assert c.apply("x", 0.0) == 0.0
    assert [(e.kind, e.time, e.source) for e in c.events] == [("activated", 2.0, "manual"), ("deactivated", 4.0, "manual")]
