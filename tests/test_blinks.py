"""눈 깜빡임 처리: 깜빡임 부분만 가리면 눈 뜬 상태의 이마 채널을 훨씬 많이 쓸 수 있어야 한다."""
from dataclasses import replace

import numpy as np

from brainfit.artifacts import artifact_mask, rising_edges
from brainfit.config import PRE
from brainfit.preprocess import filter_session, label_windows, make_windows
from brainfit.realtime.engine import RealtimeEngine
from brainfit.realtime.sources import SimSource
from brainfit.synth import synthetic_session


def _eo_frontal_ratio(cfg):
    fs = filter_session(synthetic_session(seed=5, blink_rate=0.4))  # 분당 약 24회
    _, info = make_windows(fs, cfg)
    info = label_windows(info, fs.segments)
    eo = info[info["segment"] == "rest_eo"]
    return float(eo[["good_AF7", "good_AF8"]].mean().mean()), float(eo[["good_TP9", "good_TP10"]].mean().mean())


def test_masking_recovers_frontal_windows():
    before, tp_before = _eo_frontal_ratio(replace(PRE, blink_uv=1e9))  # 가림 끔 = 예전 방식
    after, tp_after = _eo_frontal_ratio(PRE)
    assert after > before + 0.2 and after >= 0.65   # 24회/분 기준: 약 0.42 → 0.72 (15회/분이면 0.58 → 0.88)
    assert tp_after == tp_before                                     # 귀 뒤 채널 판정은 그대로


def test_mask_shape_and_events():
    sf = 256
    x = np.random.default_rng(0).normal(0, 8, (4, sf * 4))
    x[1:3, 300:370] += 200                                            # 깜빡임 1회 (이마)
    m = artifact_mask(x, ["TP9", "AF7", "AF8", "TP10"], sf)
    assert m[1].any() and m[2].any() and not m[0].any()
    assert len(rising_edges(m[1])) == 1


def test_realtime_blink_rate_and_quality():
    src, t = SimSource(seed=1, blink_rate=0.4), 0.0
    eng = RealtimeEngine(src)
    src.set_state("rest_eo")
    while t < 60:
        t += 0.25
        eng.pump(t)
    snap = eng.snapshot()
    assert snap["quality"]["AF7"] >= 0.7 and snap["quality_status"] == "good"
    assert 12 <= snap["blinks_per_min"] <= 36                        # 실제 약 24회/분
