"""알려진 뇌파 현상을 가짜 데이터에서 코드가 제대로 잡아내는지 검증.
실제 데이터를 바꿔도 이 테스트들은 '분석 코드가 망가지지 않았는지' 지켜 준다."""
import numpy as np

from brainfit.cognitive import dprime
from brainfit.io import Session, add_manual_segments, format_marker, parse_marker


def test_marker_roundtrip():
    m = format_marker("trial", task="nback2", block=1, rt=0.53)
    d = parse_marker(m)
    assert d == {"event": "trial", "task": "nback2", "block": 1, "rt": 0.53}


def test_dprime_monotonic():
    assert dprime(9, 10, 1, 30) > dprime(6, 10, 5, 30) > 0


def test_baseline_alpha_reactivity_and_iaf(result):
    b = result["baseline"]
    assert b["alpha_reactivity"] > 1.5          # 눈 감으면 알파 증가 (Berger 효과)
    assert abs(b["iaf_peak"] - 9.0) < 0.6       # 생성 시 넣은 IAF=9Hz 복원


def test_workload_increases_with_difficulty(result):
    zf = result["feats"]
    blk = zf[(zf["segment"] == "block") & zf["good"]]
    by = blk.groupby("task")["z_log_workload"].mean()
    assert by["nback2"] > by["nback1"]


def test_fatigue_trend_positive(result):
    assert result["fatigue"]["fatigue_slope_per_10min"] > 0
    assert result["fatigue"]["ec_alpha_change_pct"] > 0


def test_hexagon_profile(result):
    p = result["profile"]
    assert len(p["axes"]) == 6
    for ax in p["axes"].values():
        assert ax["score"] is None or 0 <= ax["score"] <= 100
    assert p["composite_behavior"] is not None
    assert p["sustained_min"] is not None


def test_p300_detected(result):
    e = result["erp"]
    assert e["valid"] and e["p300_amp_uv"] > 2.0
    assert 250 <= e["p300_latency_ms"] <= 500


def test_behavior_metrics(result):
    beh = result["behavior"].set_index("task")
    assert beh.loc["gonogo", "fa_rate"] > beh.loc["oddball", "fa_rate"]  # No-Go 가 더 어려움
    assert beh.loc["gonogo", "rt_median"] < 0.6


def test_xdf_roundtrip(tmp_path, synth):
    from brainfit.io import load_xdf
    from brainfit.xdfwrite import session_to_xdf
    p = session_to_xdf(synth, tmp_path / "s.xdf")
    s = load_xdf(p)
    assert s.raw.ch_names == ["TP9", "AF7", "AF8", "TP10"]   # Right AUX 제외
    assert np.abs(s.raw.get_data()).max() < 1e-2              # µV → V 변환됨
    assert set(s.segments["name"]) >= {"rest_eo", "rest_ec", "block"}
    assert set(s.segments["task"].dropna()) >= {"gonogo", "nback1", "nback2", "oddball"}


def test_manual_segments(synth):
    s = Session(synth.raw, synth.events.iloc[0:0], {})
    s = add_manual_segments(s, "rest_eo:2-62,block:nback2:210-276")
    assert list(s.segments["name"]) == ["rest_eo", "block"]
