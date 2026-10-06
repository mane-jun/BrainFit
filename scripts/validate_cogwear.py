"""CogWear(Muse S, 휴식 vs Stroop)로 우리 지표가 '인지 부하'를 잡는지 검증.

  python scripts/download_datasets.py --dataset cogwear
  python scripts/validate_cogwear.py --root data/external/cogwear

검증 질문
  Q1 Stroop 중 engagement·workload 가 휴식보다 높은가?  (사람 단위 Wilcoxon, 창 단위 통계 금지)
  Q2 상대 파워: 과제 중 알파↓·베타↑ 경향이 있는가?
  Q3 '개인 기준 정규화'가 분류 성능을 올리는가? (LOSO: 사람 단위로 학습/평가 분리)
결과: outputs/validation/cogwear/ 에 summary.csv, report.json, report.md, 그림 4장
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
from brainfit.datasets import cogwear  # noqa: E402
from brainfit.fonts import setup_korean_font  # noqa: E402
from brainfit.report import compute_features  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
Z_METRICS = ["log_engagement", "log_workload", "log_fatigue"]
REL = ["theta_rel", "alpha_rel", "beta_rel"]
CLF_FEATS = ([f"{b}_{c}" for b in ("theta", "alpha", "beta") for c in MUSE_EEG_CHANNELS]
             + ["log_engagement", "log_fatigue"])


def segment_windows(feats: pd.DataFrame, name: str) -> pd.DataFrame:
    return feats[(feats["segment"] == name) & feats["good"]].copy()


def analyze_pair(base_path: str, task_path: str) -> tuple[dict, pd.DataFrame]:
    sb = cogwear.load_recording(base_path, "baseline")
    st = cogwear.load_recording(task_path, "cognitive_load")
    _, fb = compute_features(sb)
    _, ft = compute_features(st)
    wb, wt = segment_windows(fb, "rest_eo"), segment_windows(ft, "block")
    row = {"n_win_base": len(wb), "n_win_task": len(wt),
           "good_ratio_base": round(float(fb["good"].mean()), 3),
           "good_ratio_task": round(float(ft["good"].mean()), 3),
           "srate_base": sb.meta.get("effective_srate"), "srate_task": st.meta.get("effective_srate")}
    for c in MUSE_EEG_CHANNELS:
        row[f"hsi_good_{c}"] = st.meta.get(f"hsi_good_{c}")
    if len(wb) < 10 or len(wt) < 10:
        row["skip"] = "창 부족"
        return row, pd.DataFrame()
    for m in Z_METRICS:  # 과제 창을 '같은 사람 휴식' 기준 z 로
        mu, sd = wb[m].mean(), wb[m].std(ddof=1)
        row[f"z_{m}"] = round(float(((wt[m] - mu) / sd).mean()), 3) if sd > 0 else np.nan
    for m in REL:
        row[f"{m}_base"] = round(float(wb[m].mean()), 4)
        row[f"{m}_task"] = round(float(wt[m].mean()), 4)

    # 분류용 창 데이터: 로그 대역 파워(채널별) + 비율 지표
    keep = [c for c in CLF_FEATS if c in wb]
    wb_x, wt_x = wb[keep].copy(), wt[keep].copy()
    for c in keep[:12]:
        wb_x[c], wt_x[c] = np.log(wb_x[c]), np.log(wt_x[c])
    wb_x["label"], wt_x["label"] = 0, 1
    win = pd.concat([wb_x, wt_x], ignore_index=True)
    # 개인 정규화 버전: 이 녹화의 '휴식 창' 평균·SD 로 표준화 (= 첫 측정 보정 단계)
    mu, sd = wb_x[keep].mean(), wb_x[keep].std(ddof=1).replace(0, np.nan)
    for c in keep:
        win[f"norm_{c}"] = (win[c] - mu[c]) / sd[c]
    return row, win


def loso(windows: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    out = []
    data = windows.dropna(subset=cols)
    for pid in sorted(data["participant"].unique()):
        tr, te = data[data["participant"] != pid], data[data["participant"] == pid]
        if te["label"].nunique() < 2 or tr["label"].nunique() < 2:
            continue
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
        clf.fit(tr[cols], tr["label"])
        out.append({"participant": pid,
                    "balanced_acc": balanced_accuracy_score(te["label"], clf.predict(te[cols]))})
    return pd.DataFrame(out)


def figures(summ: pd.DataFrame, clf: dict, out: Path):
    setup_korean_font()
    per = summ.groupby("participant")[[f"z_{m}" for m in Z_METRICS]].mean()
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, m in enumerate(Z_METRICS):
        v = per[f"z_{m}"].dropna()
        ax.scatter(np.full(len(v), i) + np.random.uniform(-0.12, 0.12, len(v)), v, alpha=0.7)
        ax.hlines(v.median(), i - 0.25, i + 0.25, color="k", lw=2)
    ax.axhline(0, c="gray", ls="--")
    ax.set_xticks(range(3), ["Engagement\nβ/(α+θ)", "Workload\nθ_AF/α_TP", "Fatigue\n(θ+α)/β"])
    ax.set_ylabel("Stroop 중 z (본인 휴식 기준)")
    ax.set_title("CogWear: 휴식 대비 Stroop — 사람별 점, 막대=중앙값")
    fig.tight_layout()
    fig.savefig(out / "01_z_metrics.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), sharey=False)
    per_rel = summ.groupby("participant")[[f"{m}_{k}" for m in REL for k in ("base", "task")]].mean()
    for ax, m in zip(axes, REL, strict=True):
        for _, r in per_rel.iterrows():
            ax.plot([0, 1], [r[f"{m}_base"] * 100, r[f"{m}_task"] * 100], c="#4c72b0", alpha=0.5, marker="o")
        ax.set_xticks([0, 1], ["휴식", "Stroop"])
        ax.set_title(m.replace("_rel", " 상대파워 (%)"))
    fig.tight_layout()
    fig.savefig(out / "02_relative_power.png", dpi=130)
    plt.close(fig)

    if clf:
        fig, ax = plt.subplots(figsize=(5, 3.6))
        names, means = list(clf), [clf[k]["mean"] for k in clf]
        sds = [clf[k]["sd"] for k in clf]
        ax.bar(names, means, yerr=sds, color=["#999999", "#4c72b0"], capsize=6)
        ax.axhline(0.5, c="r", ls="--", lw=1, label="우연 수준")
        ax.set_ylim(0, 1)
        ax.set_ylabel("균형 정확도 (LOSO)")
        ax.set_title("휴식 vs Stroop 분류: 개인 정규화 효과")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "03_classifier.png", dpi=130)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.4))
    q = summ.set_index(summ["participant"] + "_" + summ["session"])[["good_ratio_base", "good_ratio_task"]]
    q.plot.bar(ax=ax, color=["#8fb3d9", "#f0a868"])
    ax.axhline(0.6, c="r", ls="--", lw=1)
    ax.set_ylim(0, 1)
    ax.set_title("녹화별 사용 가능 창 비율")
    ax.tick_params(axis="x", labelsize=7)
    fig.tight_layout()
    fig.savefig(out / "04_quality.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/external/cogwear")
    ap.add_argument("--out", default="outputs/validation/cogwear")
    ap.add_argument("--max", type=int, default=None, help="빠른 점검용: 녹화 쌍 개수 제한")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    recs = cogwear.find_recordings(a.root)
    if recs.empty:
        sys.exit(f"{a.root} 에서 muse_eeg.csv 를 찾지 못했습니다. download_datasets.py 를 먼저 실행하세요.")
    pairs = recs[recs["condition"].isin(["baseline", "cognitive_load"])].pivot_table(
        index=["participant", "study", "session"], columns="condition", values="path", aggfunc="first"
    ).dropna().reset_index()
    if a.max:
        pairs = pairs.head(a.max)
    print(f"[cogwear] 휴식+Stroop 쌍 {len(pairs)}개")

    rows, wins = [], []
    for _, p in pairs.iterrows():
        tag = f"{p['participant']}/{p['session']}"
        try:
            row, win = analyze_pair(p["baseline"], p["cognitive_load"])
        except Exception as e:  # noqa: BLE001 — 한 파일 오류로 전체를 멈추지 않음
            print(f"  {tag}: 실패 {e}")
            continue
        row.update({"participant": p["participant"], "study": p["study"], "session": p["session"]})
        stroop = Path(p["cognitive_load"]).with_name("stroop_responses.csv")
        if stroop.exists():
            row.update({f"stroop_{k}": v for k, v in cogwear.load_stroop(stroop).items()})
        rows.append(row)
        if not win.empty:
            win["participant"] = p["participant"]
            wins.append(win)
        print(f"  {tag}: 창 {row['n_win_base']}/{row['n_win_task']}, "
              f"engagement z={row.get('z_log_engagement')}, workload z={row.get('z_log_workload')}")

    summ = pd.DataFrame(rows)
    summ.to_csv(out / "summary.csv", index=False)
    ok = summ[summ.get("skip").isna()] if "skip" in summ else summ

    # Q1·Q2: 사람 단위 검정 (같은 사람의 여러 세션은 평균)
    per = ok.groupby("participant").mean(numeric_only=True)
    tests = {}
    for m in Z_METRICS:
        v = per[f"z_{m}"].dropna()
        if len(v) >= 5:
            tests[m] = {"n_people": len(v), "median_z": round(float(v.median()), 3),
                        "n_positive": int((v > 0).sum()), "wilcoxon_p": float(wilcoxon(v).pvalue)}
    for m in REL:
        d = (per[f"{m}_task"] - per[f"{m}_base"]).dropna()
        if len(d) >= 5:
            tests[f"{m}_change"] = {"n_people": len(d), "median_diff_pctpt": round(float(d.median() * 100), 2),
                                    "wilcoxon_p": float(wilcoxon(d).pvalue)}

    # Q3: LOSO 분류
    clf = {}
    if wins:
        W = pd.concat(wins, ignore_index=True)
        raw_cols = [c for c in CLF_FEATS if c in W]
        for name, cols in (("원시 특징", raw_cols), ("개인 정규화", [f"norm_{c}" for c in raw_cols])):
            r = loso(W, cols)
            if not r.empty:
                clf[name] = {"mean": round(float(r["balanced_acc"].mean()), 3),
                             "sd": round(float(r["balanced_acc"].std(ddof=1)), 3), "n_people": len(r)}
    report = {"n_pairs": int(len(summ)), "n_people": int(per.shape[0]), "tests": tests, "classifier": clf,
              "note": "사람 단위 통계만 사용. CogWear 는 Stroop→휴식 순서라 휴식에 과제 여운이 섞일 수 있음."}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    figures(ok, clf, out)

    lines = ["# CogWear 검증 결과", "", f"- 녹화 쌍 {report['n_pairs']}개, 참가자 {report['n_people']}명", ""]
    lines += ["| 지표 | 사람 수 | 중앙값 | 양수 인원 / 변화 | p (Wilcoxon) |", "|---|---|---|---|---|"]
    for k, v in tests.items():
        mid = v.get("median_z", v.get("median_diff_pctpt"))
        lines.append(f"| {k} | {v['n_people']} | {mid} | {v.get('n_positive', '-')} | {v['wilcoxon_p']:.3g} |")
    lines += ["", "| 분류(LOSO) | 균형 정확도 | 사람 수 |", "|---|---|---|"]
    lines += [f"| {k} | {v['mean']} ± {v['sd']} | {v['n_people']} |" for k, v in clf.items()]
    lines += ["", "그림: 01_z_metrics.png, 02_relative_power.png, 03_classifier.png, 04_quality.png"]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
