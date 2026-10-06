"""ERP(사건관련전위) 분석 — Visual Oddball 의 P300.

Muse 로 P300 측정이 가능하다는 보고(Krigolson et al., 2017)가 있지만, 4채널·건식 전극이라
시행 수가 충분하고 잡음 에포크를 엄격히 버려야 한다. 깨끗한 타깃 에포크가
ERP_MIN_TARGET_EPOCHS 미만이면 결과를 '측정 불충분'으로 처리한다.

⚠️ 블루투스 지연 때문에 절대 잠복기(ms)는 임상 연구값과 비교할 수 없다.
   같은 장비·같은 프로그램으로 잰 '본인 이전 기록'과의 비교에만 쓴다.
"""
from __future__ import annotations

import numpy as np

from .config import ERP_MIN_TARGET_EPOCHS, TEMPORO_PARIETAL
from .io import Session


def condition_erp(sess: Session, onsets: dict[str, np.ndarray], picks: list[str],
                  tmin: float = -0.2, tmax: float = 0.8, l_freq: float = 0.5, h_freq: float = 15.0,
                  reject_uv: float = 100.0, average_channels: bool = True) -> dict:
    """조건별 ERP. onsets = {"related": [초...], "unrelated": [초...]}

    반환: times, waves[cond] (n_ch or 1, n_t), n_clean[cond], epochs[cond] (단일 시행, 통계용)
    """
    raw = sess.raw.copy().load_data()
    raw.filter(l_freq, h_freq, fir_design="firwin", verbose=False)
    picks = [c for c in picks if c in raw.ch_names]
    x = raw.get_data(picks=picks) * 1e6
    sf = raw.info["sfreq"]
    i0, i1 = int(round(tmin * sf)), int(round(tmax * sf))
    times = np.arange(i0, i1) / sf
    out = {"times": times, "picks": picks, "waves": {}, "n_clean": {}, "n_total": {}, "epochs": {}}
    for cond, ons in onsets.items():
        eps = []
        for t in np.asarray(ons, float):
            c = int(round(t * sf))
            if c + i0 < 0 or c + i1 > x.shape[1]:
                continue
            ep = x[:, c + i0:c + i1]
            ep = ep - ep[:, times < 0].mean(axis=1, keepdims=True)  # 자극 전 기준선 보정
            if np.ptp(ep, axis=1).max() > reject_uv:
                continue
            eps.append(ep.mean(axis=0, keepdims=True) if average_channels else ep)
        eps = np.array(eps)  # (n_ep, n_ch', n_t)
        out["n_total"][cond] = int(len(ons))
        out["n_clean"][cond] = int(len(eps))
        out["epochs"][cond] = eps
        out["waves"][cond] = eps.mean(axis=0) if len(eps) else None
    return out


def window_mean(times: np.ndarray, wave: np.ndarray, window: tuple[float, float]) -> np.ndarray:
    w = (times >= window[0]) & (times <= window[1])
    return wave[..., w].mean(axis=-1)


def oddball_erp(sess: Session, task: str = "oddball", tmin: float = -0.2, tmax: float = 0.8,
                l_freq: float = 0.5, h_freq: float = 15.0, reject_uv: float = 100.0,
                window: tuple[float, float] = (0.25, 0.50)) -> dict:
    ev = sess.events
    if "task" not in ev:
        return {"valid": False, "reason": "no_task_markers"}
    stims = ev[(ev["event"] == "stim") & (ev["task"] == task)]
    if stims.empty:
        return {"valid": False, "reason": "no_oddball"}
    picks = [c for c in TEMPORO_PARIETAL if c in sess.raw.ch_names]
    tgt_on = stims.loc[stims["target"] == 1, "onset"].to_numpy()
    std_on = stims.loc[stims["target"] == 0, "onset"].to_numpy()
    r = condition_erp(sess, {"target": tgt_on, "standard": std_on}, picks, tmin, tmax,
                      l_freq, h_freq, reject_uv)
    times = r["times"]
    n_t, n_s = r["n_clean"]["target"], r["n_clean"]["standard"]
    out = {"n_target_clean": n_t, "n_standard_clean": n_s,
           "n_target_total": r["n_total"]["target"], "times": times}
    if n_t == 0 or n_s == 0:
        return dict(out, valid=False, reason="no_clean_epochs")
    tgt, std = r["waves"]["target"][0], r["waves"]["standard"][0]
    diff = tgt - std
    w = (times >= window[0]) & (times <= window[1])
    k = int(np.argmax(diff[w]))
    out.update({"target_wave": tgt, "standard_wave": std, "diff_wave": diff,
                "p300_amp_uv": round(float(diff[w].mean()), 2),       # 구간 평균(잡음에 강함)
                "p300_peak_uv": round(float(diff[w][k]), 2),
                "p300_latency_ms": round(float(times[w][k] * 1000), 0),
                "valid": n_t >= ERP_MIN_TARGET_EPOCHS})
    if not out["valid"]:
        out["reason"] = f"clean target epochs {n_t} < {ERP_MIN_TARGET_EPOCHS}"
    return out
