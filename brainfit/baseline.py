"""[세부내용 1번] 사용자 기본 뇌파(기준선) 측정·분석.

1) 이번 세션 기준선: 눈 뜬 휴식(EO) / 눈 감은 휴식(EC) 구간에서
   - IAF(개인 알파 피크 주파수), 알파 반응성(EC/EO), 대역별 상대 파워
   - 과제 분석 때 z 점수의 기준이 될 EO 지표 분포(평균·표준편차)
2) 개인 기준선 누적: 세션이 쌓이면 '나의 평소'를 계산해 오늘 상태를 비교
3) 집단 참고값: 처음 1~2회는 개인 이력이 없으므로 공개 데이터/문헌값을 '참고'로만 쓴다
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import COG, TEMPORO_PARIETAL
from .features import band_power, individual_alpha_frequency, segment_spectrum
from .io import Session

BASELINE_METRICS = ["log_engagement", "log_workload", "log_fatigue",
                    "theta_rel", "alpha_rel", "beta_rel"]

# 집단 참고값(초기값). IAF 는 건강한 성인 약 10 Hz 전후(Klimesch, 1999).
# 나머지는 scripts/build_population_ref.py 로 공개 데이터에서 계산해 채운다.
POPULATION_REF: dict[str, dict] = {
    "iaf_peak": {"mean": 10.0, "sd": 1.0, "source": "Klimesch 1999 (literature)"},
}


def _seg(segments: pd.DataFrame, name: str):
    s = segments[segments["name"] == name]
    return None if s.empty else s.iloc[0]


def compute_baseline(sess: Session, feats: pd.DataFrame) -> dict:
    segs = sess.segments
    eo, ec = _seg(segs, "rest_eo"), _seg(segs, "rest_ec")
    out: dict = {"has_eo": eo is not None, "has_ec": ec is not None}
    tp = [c for c in TEMPORO_PARIETAL if c in sess.raw.ch_names]

    spectra = {}
    for name, sg in (("eo", eo), ("ec", ec)):
        if sg is None:
            continue
        # 앞뒤 5초는 지시 전환 영향이 있어 잘라낸다
        f, p = segment_spectrum(sess, sg["start"] + 5, sg["end"] - 2, picks=tp or None)
        spectra[name] = (f, p.mean(axis=0))
        out[f"alpha_{name}"] = float(band_power(f, p.mean(axis=0), 8, 13))

    if "ec" in spectra:
        out.update(individual_alpha_frequency(*spectra["ec"]))
    if "eo" in spectra and "ec" in spectra:
        out["alpha_reactivity"] = round(out["alpha_ec"] / (out["alpha_eo"] + 1e-12), 2)

    ref = feats[(feats["segment"] == "rest_eo") & feats["good"]]
    out["eo_n_windows"] = int(len(ref))
    out["eo_stats"] = {m: {"mean": float(ref[m].mean()), "sd": float(ref[m].std(ddof=1))}
                       for m in BASELINE_METRICS if m in ref and len(ref) > 2}
    out["_spectra"] = spectra  # 그림용(저장하지 않음)
    return out


def zscore(feats: pd.DataFrame, stats: dict, metrics=BASELINE_METRICS) -> pd.DataFrame:
    """각 지표를 '이번 세션 EO 휴식' 기준 z 점수로. 사람 간 차이를 지우는 핵심 단계."""
    out = feats.copy()
    for m in metrics:
        if m in stats and stats[m]["sd"] and np.isfinite(stats[m]["sd"]):
            out[f"z_{m}"] = (out[m] - stats[m]["mean"]) / stats[m]["sd"]
    return out


class BaselineStore:
    """사용자별 세션 요약을 쌓아 '나의 평소'를 만든다. data/users/<user>/history.json"""

    KEYS = ["iaf_peak", "alpha_reactivity", "alpha_eo", "alpha_ec", "composite_behavior",
            "sustained_min", "engagement_task_z", "axis_speed", "axis_inhibition", "axis_wm",
            "axis_attention", "axis_sustain", "axis_p300"]

    def __init__(self, root: str | Path, user: str):
        self.path = Path(root) / user / "history.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.history: list[dict] = (json.loads(self.path.read_text(encoding="utf-8"))
                                    if self.path.exists() else [])

    def add(self, summary: dict) -> None:
        row = {k: summary.get(k) for k in self.KEYS}
        row["time"] = datetime.now().isoformat(timespec="seconds")
        self.history.append(row)
        self.path.write_text(json.dumps(self.history, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def reference(self, key: str, last_n: int = 10) -> dict | None:
        vals = [h[key] for h in self.history[-last_n:] if h.get(key) is not None]
        if len(vals) < COG.min_history_sessions:
            return None
        return {"mean": float(np.mean(vals)), "sd": float(np.std(vals, ddof=1)) or 1e-6,
                "n": len(vals)}

    def compare(self, current: dict) -> dict:
        """오늘 값 vs 나의 평소(이력 ≥3) — 없으면 집단 참고값으로 대체하고 표시."""
        res = {}
        for k in self.KEYS:
            v = current.get(k)
            if v is None:
                continue
            ref, src = self.reference(k), "personal"
            if ref is None and k in POPULATION_REF:
                ref, src = POPULATION_REF[k], "population"
            if ref is None:
                res[k] = {"value": v, "z": None, "ref": "insufficient_history"}
            else:
                res[k] = {"value": v, "z": round((v - ref["mean"]) / ref["sd"], 2), "ref": src}
        return res
