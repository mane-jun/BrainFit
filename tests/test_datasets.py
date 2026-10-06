"""공개 데이터 로더·검증 스크립트 테스트 (실제 형식을 흉내 낸 가짜 파일 사용)."""
import json
import subprocess
import sys
from pathlib import Path

from fake_datasets import make_cogwear_tree, write_mind_monitor_csv, write_n400_xdf

from brainfit.datasets import cogwear, muse_n400
from brainfit.erp import condition_erp, window_mean
from brainfit.io import list_streams

ROOT = Path(__file__).resolve().parents[1]


def test_mind_monitor_reader(tmp_path):
    p = tmp_path / "muse_eeg.csv"
    write_mind_monitor_csv(p, "baseline", seed=0, sec=20)
    x, info = cogwear.read_mind_monitor_csv(p)
    assert x.shape == (4, 20 * 256)               # 이벤트 행 제거
    assert info["hsi_good_TP9"] == 1.0
    s = cogwear.load_recording(p, "baseline")
    assert list(s.segments["name"]) == ["rest_eo"]
    assert abs(s.raw.get_data().mean()) < 1e-2     # µV → V


def test_find_recordings_and_stroop(tmp_path):
    make_cogwear_tree(tmp_path, n_people=2)
    recs = cogwear.find_recordings(tmp_path)
    assert len(recs) == 4 and set(recs["condition"]) == {"baseline", "cognitive_load"}
    st = cogwear.load_stroop(tmp_path / "pilot/0/cognitive_load/stroop_responses.csv")
    assert st["interference_ms"] == 130.0 and st["accuracy"] == 0.9


def test_validate_cogwear_script(tmp_path):
    make_cogwear_tree(tmp_path / "cw", n_people=6)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/validate_cogwear.py"), "--root",
                        str(tmp_path / "cw"), "--out", str(out)], capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["tests"]["log_engagement"]["median_z"] > 0     # 가짜 Stroop: 베타↑ 알파↓
    assert rep["classifier"]["개인 정규화"]["mean"] > 0.8
    assert (out / "01_z_metrics.png").exists()


def test_n400_xdf_loader_and_effect(tmp_path):
    p = tmp_path / "sub01.xdf"
    write_n400_xdf(p, seed=1)
    streams = list_streams(p)
    assert {s["type"] for s in streams} == {"EEG", "Markers"}
    sess = muse_n400.load(p)
    on = muse_n400.condition_onsets(sess, target_filter="target")
    assert len(on["related"]) == 56 and len(on["unrelated"]) == 56   # 'unrelated' 가 related 로 새지 않음
    r = condition_erp(sess, on, ["AF8"])
    eff = window_mean(r["times"], r["waves"]["unrelated"][0] - r["waves"]["related"][0], (0.3, 0.5))
    assert eff < -1.5


def test_validate_n400_script(tmp_path):
    d = tmp_path / "n400"
    for i in range(6):
        write_n400_xdf(d / f"sub{i:02d}.xdf", seed=i)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/validate_muse_n400.py"), "--root", str(d),
                        "--out", str(out), "--target-filter", "target"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["n_loaded"] == 6 and rep["tests"]["AF8"]["median_uv"] < 0
    assert (out / "01_grand_average.png").exists()
