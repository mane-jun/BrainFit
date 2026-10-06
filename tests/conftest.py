import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def synth():
    from brainfit.synth import synthetic_session
    return synthetic_session(seed=3, iaf=9.0)


@pytest.fixture(scope="session")
def result(synth):
    from brainfit.report import analyze
    return analyze(synth)
