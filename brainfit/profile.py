"""육각형 Brain Profile (0~100) — docs/BATTERY.md 4절.

원칙
- 4개 축(반응속도·억제조절·작업기억·주의 정확성)은 **과제 수행 성과**에서 나온다.
- '집중 유지'는 행동(반응시간 변동성) + 뇌파(휴식 대비 몰입 지표 유지율) 결합.
- '뇌 반응(P300)'은 품질 기준을 통과한 경우에만 표시, 아니면 '측정 불충분'.
- 점수 = 100 × Φ(z), z 는 연령대 기준값(HEX_REFERENCE, 현재 임시값) 대비.
- 진단이 아니다. 2회차부터는 '본인 이전 기록 대비 변화'를 더 중요하게 보여 준다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import HEX_AXES, HEX_REFERENCE

DISCLAIMER = "본 결과는 학습·훈련용 참고 지표이며 의학적 진단이 아닙니다."


def _task_mean(beh: pd.DataFrame, task: str, col: str):
    if beh.empty or col not in beh:
        return None
    v = beh.loc[beh["task"] == task, col].dropna()
    return float(v.mean()) if len(v) else None


def raw_metrics(beh: pd.DataFrame, blocks_eeg: pd.DataFrame, erp: dict) -> dict:
    m = {"gonogo_rt_median": _task_mean(beh, "gonogo", "rt_median"),
         "gonogo_commission": _task_mean(beh, "gonogo", "fa_rate"),
         "nback2_dprime": _task_mean(beh, "nback2", "dprime"),
         "oddball_dprime": _task_mean(beh, "oddball", "dprime")}
    parts = []
    cv = _task_mean(beh, "gonogo", "rt_cv")
    if cv is not None:
        parts.append(float(np.clip(1 - cv / 0.5, 0, 1)))        # 변동성 낮을수록 안정적 집중
    if not blocks_eeg.empty and "retention" in blocks_eeg:
        parts.append(float(blocks_eeg["retention"].mean()))      # 휴식보다 몰입이 높은 창 비율
    m["sustain_composite"] = float(np.mean(parts)) if parts else None
    m["p300_amp_uv"] = erp.get("p300_amp_uv") if erp.get("valid") else None
    return m


def build_profile(beh: pd.DataFrame, blocks_eeg: pd.DataFrame, sustained: dict,
                  erp: dict | None = None, age_band: str = "adult") -> dict:
    erp = erp or {}
    ref = HEX_REFERENCE[age_band]
    metrics = raw_metrics(beh, blocks_eeg, erp)
    axes = {}
    for key, ax in HEX_AXES.items():
        v = metrics.get(ax["metric"])
        if v is None or not np.isfinite(v):
            axes[key] = {"ko": ax["ko"], "score": None, "raw": None}
            continue
        mu, sd = ref[ax["metric"]]
        z = (v - mu) / sd * (1 if ax["higher_better"] else -1)
        axes[key] = {"ko": ax["ko"], "score": int(round(100 * norm.cdf(z))), "raw": round(v, 3),
                     "z": round(z, 2)}
    beh_axes = [axes[k]["score"] for k in ("speed", "inhibition", "wm", "attention")
                if axes[k]["score"] is not None]
    return {
        "age_band": age_band,
        "axes": axes,
        "scores_ko": {a["ko"]: a["score"] for a in axes.values()},
        "composite_behavior": int(round(np.mean(beh_axes))) if beh_axes else None,
        "sustained_min": sustained.get("sustained_min"),
        "sustained_censored": sustained.get("censored"),
        "unmeasured": [a["ko"] for a in axes.values() if a["score"] is None],
        "reference_note": "기준값은 임시값(파일럿 데이터로 교체 예정)",
        "disclaimer": DISCLAIMER,
    }
