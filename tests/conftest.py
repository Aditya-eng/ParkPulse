import pytest

from parkpulse.state import LiveState


@pytest.fixture(scope="session")
def state():
    return LiveState(history_days=21, seed=5)
