"""Muse 2 N400 공개 데이터(OSF u6y9g)로 load_xdf·ERP 코드를 실제 Muse 녹화에서 검증.

1단계 — 마커 확인 (먼저 1개 파일로)
  python scripts/validate_muse_n400.py --inspect data/external/muse_n400/<파일>.xdf
2단계 — 전체 실행 (마커 정규식은 1단계 결과에 맞게)
  python scripts/validate_muse_n400.py --root data/external/muse_n400 \
      --related "목표단어_관련_정규식" --unrelated "목표단어_무관_정규식"

검증 질문
  Q1 load_xdf 가 실제 BlueMuse 녹화를 문제없이 읽는가? (채널, 샘플링률, 끊김, 마커 수)
  Q2 잡음 제외 후 남는 시행이 충분한가? (원 논문 기준: 관련 24, 무관 27 시행 이상)
  Q3 무관 − 관련 차이가 300–500 ms 에서 음(−)인가? (원 논문: 오른쪽 이마 AF8 에서 유의)
결과: outputs/validation/muse_n400/ 에 loader_check.csv, subjects.csv, report.json, 그림
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402

from brainfit.config import MUSE_EEG_CHANNELS  # noqa: E402
from brainfit.datasets import muse_n400  # noqa: E402
from brainfit.erp import condition_erp, window_mean  # noqa: E402
from brainfit.fonts import setup_korean_font  # noqa: E402
from brainfit.io import list_streams  # noqa: E402
from brainfit.report import compute_features  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
MIN_TRIALS = {"related": 24, "unrelated": 27}  # Hayes & Magne 의 신뢰도 기준


def inspect(path: Path):
    print(f"\n== {path.name}")
    print(pd.DataFrame(list_streams(path)).to_string(index=False))
    sess = muse_n400.load(path)
    print("\nmeta:", {k: sess.meta.get(k) for k in ("nominal_srate", "effective_srate", "n_gaps",
                                                    "duration_s", "warning")})
    print("채널:", sess.raw.ch_names)
    cnt = muse_n400.marker_counts(sess)
    print(f"\n마커 패턴 {len(cnt)}개 (숫자는 #, 많은 순 30개):")
    for k, v in cnt.most_common(30):
        print(f"  {v:4d}  {k}")
    on = muse_n400.condition_onsets(sess)
    print(f"\n기본 정규식 분류 결과: related={len(on['related'])}, unrelated={len(on['unrelated'])}"
          "  (각 56 근처가 아니면 --related/--unrelated/--target-filter 를 지정하세요)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", type=Path, default=None)
    ap.add_argument("--root", default="data/external/muse_n400")
    ap.add_argument("--out", default="outputs/validation/muse_n400")
    ap.add_argument("--related", default=muse_n400.DEFAULT_RELATED)
    ap.add_argument("--unrelated", default=muse_n400.DEFAULT_UNRELATED)
    ap.add_argument("--target-filter", default=None, help="목표 단어 마커만 고르는 정규식(프라임 제외)")
    ap.add_argument("--window", nargs=2, type=float, default=[0.30, 0.50])
    ap.add_argument("--reject-uv", type=float, default=100.0)
    a = ap.parse_args()
    if a.inspect:
        inspect(a.inspect)
        return

    files = muse_n400.find_xdf(a.root)
    if not files:
        sys.exit(f"{a.root} 에 .xdf 가 없습니다. docs/DATASETS.md 의 다운로드 안내를 보세요.")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    win = tuple(a.window)

    checks, subj, grand = [], [], {c: {"related": [], "unrelated": []} for c in MUSE_EEG_CHANNELS}
    times = None
    for f in files:
        rec = {"file": f.name}
        try:
            sess = muse_n400.load(f)
        except Exception as e:  # noqa: BLE001
            rec["error"] = str(e)
            checks.append(rec)
            print(f"  {f.name}: 로드 실패 {e}")
            continue
        _, feats = compute_features(sess)
        rec.update({k: sess.meta.get(k) for k in ("nominal_srate", "effective_srate", "n_gaps", "duration_s")})
        rec["channels"] = ",".join(sess.raw.ch_names)
        rec["n_markers"] = int(len(sess.events))
        rec["good_window_ratio"] = round(float(feats["good"].mean()), 3)
        on = muse_n400.condition_onsets(sess, a.related, a.unrelated, a.target_filter)
        rec["n_related"], rec["n_unrelated"] = len(on["related"]), len(on["unrelated"])
        if not len(on["related"]) or not len(on["unrelated"]):
            rec["error"] = "조건 마커를 찾지 못함 → --inspect 로 확인"
            checks.append(rec)
            continue
        r = condition_erp(sess, on, MUSE_EEG_CHANNELS, tmin=-0.2, tmax=0.8, l_freq=0.5, h_freq=20.0,
                          reject_uv=a.reject_uv, average_channels=False)
        times = r["times"]
        rec["clean_related"], rec["clean_unrelated"] = r["n_clean"]["related"], r["n_clean"]["unrelated"]
        enough = all(r["n_clean"][k] >= MIN_TRIALS[k] for k in MIN_TRIALS)
        rec["enough_trials"] = enough
        checks.append(rec)
        row = {"participant": f.stem, "enough_trials": enough}
        for ci, ch in enumerate(r["picks"]):
            rel, unr = r["waves"]["related"][ci], r["waves"]["unrelated"][ci]
            row[f"effect_{ch}"] = round(float(window_mean(times, unr - rel, win)), 3)  # 음수 기대
            if enough:
                grand[ch]["related"].append(rel)
                grand[ch]["unrelated"].append(unr)
        subj.append(row)
        print(f"  {f.name}: 마커 {rec['n_related']}/{rec['n_unrelated']}, 깨끗 {rec['clean_related']}/"
              f"{rec['clean_unrelated']}, AF8 효과 {row.get('effect_AF8')} µV")

    pd.DataFrame(checks).to_csv(out / "loader_check.csv", index=False)
    S = pd.DataFrame(subj)
    S.to_csv(out / "subjects.csv", index=False)

    tests = {}
    use = S[S["enough_trials"]] if not S.empty else S
    for ch in MUSE_EEG_CHANNELS:
        col = f"effect_{ch}"
        if col in use and use[col].notna().sum() >= 5:
            v = use[col].dropna()
            tests[ch] = {"n": len(v), "median_uv": round(float(v.median()), 3),
                         "n_negative": int((v < 0).sum()), "wilcoxon_p": float(wilcoxon(v).pvalue)}
    report = {"n_files": len(files), "n_loaded": int(sum("error" not in c for c in checks)),
              "n_enough_trials": int(use.shape[0]) if not use.empty else 0,
              "window_s": list(win), "tests": tests,
              "expectation": "무관−관련 < 0 (N400 효과), 원 논문은 AF8 에서 유의"}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if times is not None and any(grand[c]["related"] for c in grand):
        setup_korean_font()
        fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True)
        for ax, ch in zip(axes.ravel(), ["AF7", "AF8", "TP9", "TP10"], strict=True):
            g = grand[ch]
            if not g["related"]:
                continue
            rel, unr = np.mean(g["related"], 0), np.mean(g["unrelated"], 0)
            ax.axvspan(win[0] * 1000, win[1] * 1000, color="#f9e6cf")
            ax.plot(times * 1000, rel, c="#4c72b0", label="관련")
            ax.plot(times * 1000, unr, c="#c44e52", label="무관")
            ax.plot(times * 1000, unr - rel, c="k", lw=2, label="무관−관련")
            ax.axhline(0, c="gray", lw=0.6)
            ax.axvline(0, c="gray", lw=0.6)
            t = tests.get(ch)
            ax.set_title(f"{ch}" + (f"  (중앙값 {t['median_uv']} µV, p={t['wilcoxon_p']:.3g})" if t else ""))
        axes[0, 0].legend(fontsize=8)
        fig.supxlabel("목표 단어 후 시간 (ms)")
        fig.supylabel("µV")
        fig.suptitle(f"Muse 2 N400 총평균 (n={report['n_enough_trials']})")
        fig.tight_layout()
        fig.savefig(out / "01_grand_average.png", dpi=130)
        plt.close(fig)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
