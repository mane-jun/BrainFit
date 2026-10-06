"""세션 분석 CLI.

예)
  python scripts/analyze_session.py --synthetic                      # 기기 없이 가짜 데이터로
  python scripts/analyze_session.py --xdf C:/EEGData/exp001/block_Default.xdf --user damwoo
  python scripts/analyze_session.py --session data/sessions/2026-10-10_damwoo
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brainfit.io import Session, add_manual_segments, load_xdf  # noqa: E402
from brainfit.report import analyze, save_report  # noqa: E402
from brainfit.synth import synthetic_session  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--xdf", help="LabRecorder .xdf 경로 (영문 경로 권장)")
    src.add_argument("--session", help="Session.save() 로 저장한 폴더")
    src.add_argument("--synthetic", action="store_true", help="가짜 데이터로 실행")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mode", default="standard", help="--synthetic 일 때 배터리 모드")
    ap.add_argument("--age-band", default="adult", choices=["adult", "senior"])
    ap.add_argument("--user", default=None, help="개인 기준선 누적용 사용자 ID")
    ap.add_argument("--out", default=None)
    ap.add_argument("--segments", default=None,
                    help='마커 없는 옛 녹화용: "rest_eo:5-65,rest_ec:70-130,block:nback2:140-200"')
    a = ap.parse_args()

    if a.xdf:
        sess = load_xdf(a.xdf)
    elif a.session:
        sess = Session.load(a.session)
    else:
        sess = synthetic_session(seed=a.seed, mode=a.mode)

    if a.segments:
        sess = add_manual_segments(sess, a.segments)
    if sess.meta.get("warning"):
        print("[경고]", sess.meta["warning"])

    out = a.out or f"outputs/{datetime.now():%Y%m%d_%H%M%S}"
    res = analyze(sess, age_band=a.age_band)
    summary = save_report(res, out, user=a.user, store_root="data/users" if a.user else None)
    print(json.dumps({"out": out, "quality": summary["quality"]["good_window_ratio"],
                      "baseline_iaf": summary["baseline"].get("iaf_peak"),
                      "alpha_reactivity": summary["baseline"].get("alpha_reactivity"),
                      "profile": summary["profile"]["scores_ko"],
                      "composite": summary["profile"]["composite_behavior"],
                      "p300": {k: summary["erp"].get(k) for k in
                               ("p300_amp_uv", "p300_latency_ms", "n_target_clean", "valid")},
                      "recommendations": [r["why"] + " → " + r["training"]
                                          for r in summary["recommendations"]],
                      "sustained_min": summary["sustained"].get("sustained_min"),
                      "answers": {k: v for k, v in summary["answers"].items() if k != "by_task"},
                      "fatigue": summary["fatigue"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
