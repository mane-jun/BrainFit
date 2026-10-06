"""과제 규칙(자극 순서, 적응형 난이도, 추천)과 과제 앱 자동 실행 테스트."""
import importlib.util
import random
import subprocess
import sys
from pathlib import Path

import pytest

from brainfit.recommend import next_nback_level, recommend
from brainfit.sequences import gonogo_sequence, oddball_sequence

ROOT = Path(__file__).resolve().parents[1]


def test_gonogo_sequence_rules():
    s = gonogo_sequence(100, 0.25, random.Random(0))
    assert len(s) == 100 and s.count(0) == 25
    for i, x in enumerate(s):
        if x == 0:  # No-Go 앞에는 Go 가 최소 2개
            assert i >= 2 and s[i - 1] == 1 and s[i - 2] == 1


def test_oddball_ratio():
    s = oddball_sequence(180, 0.2, random.Random(1))
    assert sum(s) == 36 and all(not (a and b) for a, b in zip(s, s[1:], strict=False))


def test_adaptive_nback():
    assert next_nback_level(2, 0.90, 0.5) == 3
    assert next_nback_level(2, 0.90, 2.5) == 2     # 정확해도 뇌 부하가 과하면 유지
    assert next_nback_level(2, 0.50) == 1


def test_recommend_lowest_axes():
    prof = {"axes": {"speed": {"ko": "반응속도", "score": 80}, "wm": {"ko": "작업기억", "score": 30},
                     "inhibition": {"ko": "억제조절", "score": 55}}}
    assert recommend(prof, k=1)[0]["axis"] == "wm"


@pytest.mark.skipif(importlib.util.find_spec("pygame") is None, reason="pygame 없음")
def test_battery_auto_run(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "tasks/battery.py"), "--auto", "--speed", "200",
                        "--mode", "demo", "--out", str(tmp_path), "--seed", "0"],
                       capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr
    sess = next(tmp_path.iterdir())
    text = (sess / "markers.csv").read_text(encoding="utf-8")
    for ev in ("rest_eo_start", "block_start|task=gonogo", "block_start|task=oddball", "session_end"):
        assert ev in text
