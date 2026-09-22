"""Shared helpers: build a campaign with one injector at point "x" and drive it."""
import pytest

from fiblock import Campaign, FaultInjector


def single(fault, event, effect, point="x", seed=1, name=None, **kw):
    """A campaign with one injector at ``point``."""
    return Campaign({point: FaultInjector(fault, event, effect, name=name, **kw)}, seed=seed)


def drive(campaign, point, values, times=None, host=None):
    times = list(times) if times is not None else list(range(len(values)))
    return [campaign.inject(point, v, t=float(t), host=host) for t, v in zip(times, values)]


def values(campaign, point, n, value=0.0):
    return [campaign.apply(point, value, t=float(t)) for t in range(n)]


@pytest.fixture
def make_single():
    return single
