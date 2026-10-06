"""[세부내용 3번] 집중력 및 인지 상태 분석.

질문 → 계산 방법
  Q1 어느 문제에서 집중이 가장 오래 유지되나   → 블록별 '집중 유지율'과 감소 기울기
  Q2 어느 과제에서 집중이 빠르게 떨어지나       → 블록별 engagement z 의 분당 기울기(가장 음수)
  Q3 피로가 쌓이며 뇌파가 어떻게 변하나         → 과제 누적시간 vs fatigue 지표 회귀 + 사전/사후 눈감기 알파·세타 비교
  Q4 평소 대비 오늘 상태는                      → BaselineStore.compare (baseline.py)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress, norm

from .config import COG, PRE, TEMPORO_PARIETAL, CognitiveConfig
from .features import band_power, segment_spectrum
from .io import Session


# ── 행동 지표 ────────────────────────────────────────────────────────
def dprime(hits: int, n_target: int, fas: int, n_nontarget: int) -> float:
    """신호탐지 d' (Hautus 1995 log-linear 보정: 0%·100% 방지)."""
    h = (hits + 0.5) / (n_target + 1)
    f = (fas + 0.5) / (n_nontarget + 1)
    return float(norm.ppf(h) - norm.ppf(f))


def behavior_summary(trials: pd.DataFrame) -> pd.DataFrame:
    """블록별 행동 지표. 모든 과제에서 target=1 은 '눌러야 하는 자극'이다.
    (Go/No-Go: Go=1, Oddball: 삼각형=1, N-back: 일치=1, PVT: 전부 1)"""
    if trials.empty:
        return pd.DataFrame()
    t = trials.copy()
    for c in ("target", "resp", "correct", "rt"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    rows = []
    for (task, block), g in t.groupby(["task", "block"]):
        tg, nt = g[g["target"] == 1], g[g["target"] == 0]
        hits, fas = int((tg["resp"] == 1).sum()), int((nt["resp"] == 1).sum())
        rts = g.loc[(g["target"] == 1) & (g["resp"] == 1) & (g["rt"] > 0), "rt"]
        rows.append({"task": task, "block": block, "n_trials": len(g),
                     "accuracy": float(g["correct"].mean()),
                     "hit_rate": hits / max(len(tg), 1),
                     "omission": 1 - hits / max(len(tg), 1),               # 놓친 비율
                     "fa_rate": fas / max(len(nt), 1) if len(nt) else np.nan,  # = commission
                     "dprime": dprime(hits, len(tg), fas, len(nt)) if len(nt) else np.nan,
                     "rt_mean": float(rts.mean()) if len(rts) else np.nan,
                     "rt_median": float(rts.median()) if len(rts) else np.nan,
                     "rt_cv": float(rts.std() / rts.mean()) if len(rts) > 2 else np.nan,
                     "lapses": int((rts > 0.5).sum() + (tg["resp"] == 0).sum())
                     if task == "pvt" else np.nan})
    return pd.DataFrame(rows)


# ── 뇌파 지표 ────────────────────────────────────────────────────────
def _smooth(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(max(n, 1), center=True, min_periods=max(n // 3, 1)).median()


def task_timeline(zfeats: pd.DataFrame, cfg: CognitiveConfig = COG) -> pd.DataFrame:
    """과제 구간 창만 모아 '과제 누적시간(time-on-task)' 축을 만든다."""
    tl = zfeats[(zfeats["segment"] == "block") & zfeats["good"]].copy()
    tl = tl.sort_values("t_center").reset_index(drop=True)
    tl["time_on_task_min"] = np.arange(len(tl)) * PRE.step_sec / 60.0
    n = int(cfg.smooth_sec / PRE.step_sec)
    if "z_log_engagement" in tl:
        tl["eng_smooth"] = _smooth(tl["z_log_engagement"], n)
    return tl


def sustained_attention(tl: pd.DataFrame, cfg: CognitiveConfig = COG) -> dict:
    """지속 집중 시간: 과제 초반(early_ref_sec) 대비 집중 곡선이 drop_z 아래로
    drop_hold_sec 이상 '계속' 머무는 첫 시점까지의 과제 누적시간.
    끝까지 안 떨어지면 censored=True (측정 시간 내 유지 → '최소 X분')."""
    if tl.empty or "eng_smooth" not in tl:
        return {"sustained_min": None, "censored": None}
    n_ref = int(cfg.early_ref_sec / PRE.step_sec)
    ref = tl["z_log_engagement"].iloc[:n_ref]
    mu, sd = ref.mean(), ref.std(ddof=1) or 1.0
    rel = (tl["eng_smooth"] - mu) / sd
    rel_raw = (tl["z_log_engagement"] - mu) / sd
    below = (rel < cfg.drop_z).to_numpy()
    hold = int(cfg.drop_hold_sec / PRE.step_sec)
    run = 0
    for i, b in enumerate(below):
        run = run + 1 if b else 0
        if run >= hold:
            start = i - hold + 1
            return {"sustained_min": round(float(tl["time_on_task_min"].iloc[start]), 1),
                    "censored": False, "relative_curve": rel, "relative_raw": rel_raw}
    return {"sustained_min": round(float(tl["time_on_task_min"].iloc[-1]), 1),
            "censored": True, "relative_curve": rel, "relative_raw": rel_raw}


def block_eeg_summary(zfeats: pd.DataFrame) -> pd.DataFrame:
    rows = []
    blk = zfeats[(zfeats["segment"] == "block") & zfeats["good"]]
    for (task, block), g in blk.groupby(["task", "block"]):
        g = g.sort_values("t_in_segment")
        slope = (linregress(g["t_in_segment"] / 60.0, g["z_log_engagement"]).slope
                 if len(g) > 5 else np.nan)
        rows.append({"task": task, "block": block, "n_windows": len(g),
                     "engagement_z": float(g["z_log_engagement"].mean()),
                     "workload_z": float(g.get("z_log_workload", pd.Series(np.nan)).mean()),
                     "engagement_slope_per_min": float(slope),
                     # 기준(EO 휴식)보다 집중 지표가 높은 창의 비율
                     "retention": float((g["z_log_engagement"] > 0).mean())})
    return pd.DataFrame(rows)


def fatigue_analysis(sess: Session, tl: pd.DataFrame, beh: pd.DataFrame) -> dict:
    out: dict = {}
    if len(tl) > 10 and "z_log_fatigue" in tl:
        r = linregress(tl["time_on_task_min"], tl["z_log_fatigue"])
        out.update({"fatigue_slope_per_10min": round(r.slope * 10, 3),
                    "fatigue_r": round(r.rvalue, 3), "fatigue_p": float(r.pvalue)})
    segs = sess.segments
    pre, post = segs[segs["name"] == "rest_ec"], segs[segs["name"] == "rest_ec_post"]
    if not pre.empty and not post.empty:
        tp = [c for c in TEMPORO_PARIETAL if c in sess.raw.ch_names] or None
        vals = {}
        for k, sg in (("pre", pre.iloc[0]), ("post", post.iloc[0])):
            f, p = segment_spectrum(sess, sg["start"] + 5, sg["end"] - 2, picks=tp)
            pm = p.mean(axis=0)
            vals[k] = {"alpha": band_power(f, pm, 8, 13), "theta": band_power(f, pm, 4, 8)}
        out["ec_alpha_change_pct"] = round(100 * (vals["post"]["alpha"] / vals["pre"]["alpha"] - 1), 1)
        out["ec_theta_change_pct"] = round(100 * (vals["post"]["theta"] / vals["pre"]["theta"] - 1), 1)
    if not beh.empty:
        half = len(beh) // 2
        if half:
            out["accuracy_first_half"] = round(float(beh["accuracy"].iloc[:half].mean()), 3)
            out["accuracy_second_half"] = round(float(beh["accuracy"].iloc[half:].mean()), 3)
    return out


def answer_questions(blocks: pd.DataFrame) -> dict:
    """Q1·Q2 를 '과제 종류' 단위로 요약 (같은 과제 블록이 여러 개면 평균)."""
    if blocks.empty:
        return {}
    by_task = blocks.groupby("task")[["engagement_z", "engagement_slope_per_min",
                                      "retention"]].mean()
    return {
        "longest_focus_task": str(by_task["retention"].idxmax()),
        "fastest_decline_task": str(by_task["engagement_slope_per_min"].idxmin()),
        "by_task": by_task.round(3).to_dict(orient="index"),
    }
