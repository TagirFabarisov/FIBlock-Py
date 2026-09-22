import pytest


def run(campaign, target, values, times=None, host=None):
    """Drive a campaign over a sequence of values; return the list of outcomes."""
    times = list(times) if times is not None else list(range(len(values)))
    out = []
    for t, v in zip(times, values):
        out.append(campaign.inject(target, v, t=float(t), host=host))
    return out


@pytest.fixture
def drive():
    return run
