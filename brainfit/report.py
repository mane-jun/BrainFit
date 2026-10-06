"""전체 파이프라인: Session → 전처리 → 특징 → 기준선(1번) → 인지 상태(3번) → 프로필 → 그림/JSON."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from . import viz
from .baseline import BaselineStore, compute_baseline, zscore
from .cognitive import (
    answer_questions,
    behavior_summary,
    block_eeg_summary,
    fatigue_analysis,
    sustained_attention,
    task_timeline,
)
from .config import COG
from .erp import oddball_erp
from .features import window_features
from .io import Session
from .preprocess import filter_session, label_windows, make_windows, quality_report
from .profile import build_profile
from .recommend import recommend


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items() if not str(k).startswith("_")
                and k not in ("relative_curve", "relative_raw")}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def compute_features(sess: Session):
    """필터 → 창 → 구간 라벨 → 창별 특징. (공개 데이터 검증 스크립트도 이 함수를 쓴다)"""
    fs = filter_session(sess)
    win, info = make_windows(fs)
    info = label_windows(info, fs.segments)
    feats = window_features(win, info, fs.raw.ch_names, fs.raw.info["sfreq"])
    return fs, feats


def analyze(sess: Session, age_band: str = "adult") -> dict:
    fs, feats = compute_features(sess)
    ch = fs.raw.ch_names
    quality = quality_report(feats, ch)

    base = compute_baseline(fs, feats)
    zf = zscore(feats, base.get("eo_stats", {}))

    tl = task_timeline(zf)
    sustained = sustained_attention(tl)
    beh = behavior_summary(fs.trials)
    blocks = block_eeg_summary(zf) if "z_log_engagement" in zf else beh.iloc[0:0]
    fatigue = fatigue_analysis(fs, tl, beh)
    answers = answer_questions(blocks)
    erp = oddball_erp(sess)  # 원신호에서 ERP 용 필터를 따로 적용
    profile = build_profile(beh, blocks, sustained, erp, age_band)
    recs = recommend(profile)

    return {"session": fs, "feats": zf, "timeline": tl, "quality": quality,
            "baseline": base, "sustained": sustained, "behavior": beh,
            "blocks": blocks, "fatigue": fatigue, "answers": answers, "profile": profile,
            "erp": erp, "recommendations": recs}


def save_report(res: dict, out_dir: str | Path, user: str | None = None,
                store_root: str | Path | None = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fs = res["session"]
    figs = {
        "01_quality": viz.fig_quality(res["quality"], fs.raw.ch_names),
        "02_baseline_spectrum": viz.fig_baseline_spectrum(res["baseline"]),
        "03_band_timeline": viz.fig_band_timeline(res["feats"], fs.segments),
        "04_engagement": viz.fig_engagement(res["timeline"], res["sustained"], COG.drop_z),
        "05_blocks": viz.fig_blocks(res["blocks"], res["behavior"]),
        "06_fatigue": viz.fig_fatigue(res["timeline"], res["fatigue"]),
        "07_profile": viz.fig_profile_radar(res["profile"]),
        "08_erp": viz.fig_erp(res["erp"]),
    }
    for name, fig in figs.items():
        fig.savefig(out / f"{name}.png", dpi=130)
        plt.close(fig)

    b = res["baseline"]
    summary = {
        "meta": fs.meta,
        "quality": res["quality"],
        "baseline": {k: v for k, v in b.items() if not k.startswith("_")},
        "sustained": res["sustained"],
        "fatigue": res["fatigue"],
        "answers": res["answers"],
        "profile": res["profile"],
        "recommendations": res["recommendations"],
        "erp": {k: v for k, v in res["erp"].items()
                if not isinstance(v, np.ndarray)},
        "behavior": res["behavior"].to_dict(orient="records"),
        "blocks": res["blocks"].to_dict(orient="records"),
    }
    if user and store_root:
        store = BaselineStore(store_root, user)
        current = {"iaf_peak": b.get("iaf_peak"), "alpha_reactivity": b.get("alpha_reactivity"),
                   "alpha_eo": b.get("alpha_eo"), "alpha_ec": b.get("alpha_ec"),
                   "composite_behavior": res["profile"].get("composite_behavior"),
                   **{f"axis_{k}": a["score"] for k, a in res["profile"]["axes"].items()},
                   "sustained_min": res["sustained"].get("sustained_min"),
                   "engagement_task_z": (float(res["blocks"]["engagement_z"].mean())
                                         if not res["blocks"].empty else None)}
        summary["vs_usual"] = store.compare(current)  # 저장 전에 비교(오늘 값이 평소에 섞이지 않게)
        store.add(current)
    summary = _jsonable(summary)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    res["features_path"] = out / "features.csv"
    res["feats"].to_csv(res["features_path"], index=False)
    return summary
