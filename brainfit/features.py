"""특징 추출: 창별 대역 파워 → 지표(engagement, workload, fatigue, FAA), 휴식 스펙트럼 → IAF.

지표 정의와 근거 논문은 docs/METRICS.md 에 있다. 식을 바꾸면 그 문서도 같이 바꾼다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import welch

from .config import ALPHA_SEARCH, BANDS, FRONTAL, TEMPORO_PARIETAL
from .io import Session

EPS = 1e-12


def window_psd(win: np.ndarray, sfreq: float, masks: np.ndarray | None = None):
    """win: (n_win, n_ch, n_samp) V → freqs, psd (n_win, n_ch, n_freq) [µV²/Hz]

    1초 조각마다 스펙트럼을 구해 평균한다(=Welch). masks 가 있으면 0.25초 간격 조각 중
    가린 샘플이 하나라도 있는 조각은 빼고 평균한다 → 깜빡임 부분만 제외.
    깨끗한 조각이 하나도 없으면 NaN."""
    nper = min(win.shape[-1], int(sfreq))  # 1초 세그먼트 → 1 Hz 해상도, 2초 창에서 3개 평균
    if masks is None:
        return welch(win * 1e6, fs=sfreq, nperseg=nper, noverlap=nper // 2, axis=-1)
    starts = list(range(0, win.shape[-1] - nper + 1, nper // 4))  # 0.25초 간격 → 깨끗한 1초를 더 잘 찾음
    segs = np.stack([win[..., s:s + nper] for s in starts], axis=-2) * 1e6   # (.., n_seg, nper)
    f, p = welch(segs, fs=sfreq, nperseg=nper, noverlap=0, axis=-1)         # (.., n_seg, n_f)
    valid = np.stack([~masks[..., s:s + nper].any(-1) for s in starts], axis=-1)
    p = np.where(valid[..., None], p, np.nan)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return f, np.nanmean(p, axis=-2)


def band_power(f: np.ndarray, psd: np.ndarray, lo: float, hi: float) -> np.ndarray:
    m = (f >= lo) & (f < hi)
    return np.trapezoid(psd[..., m], f[m], axis=-1)


def window_features(win: np.ndarray, info: pd.DataFrame, ch_names: list[str],
                    sfreq: float, masks: np.ndarray | None = None) -> pd.DataFrame:
    """창마다 채널별 대역 파워와 파생 지표를 계산. 나쁜 채널 값은 NaN.
    masks(n_win, n_ch, n_samp, True=가림)가 있으면 깜빡임 부분을 뺀 조각들로 계산."""
    f, psd = window_psd(win, sfreq, masks)
    good = np.stack([info[f"good_{c}"].to_numpy() for c in ch_names], axis=1)  # (n_win, n_ch)
    total = band_power(f, psd, 1.0, 40.0)
    out = info.copy()
    bp = {}
    for b, (lo, hi) in BANDS.items():
        v = band_power(f, psd, lo, hi)
        v = np.where(good, v, np.nan)
        bp[b] = v
        for ci, ch in enumerate(ch_names):
            out[f"{b}_{ch}"] = v[:, ci]
        out[f"{b}_rel"] = np.nanmean(v / np.where(good, total, np.nan), axis=1)
        out[f"{b}_abs"] = np.nanmean(v, axis=1)

    idx = {c: i for i, c in enumerate(ch_names)}
    fr = [idx[c] for c in FRONTAL if c in idx]
    tp = [idx[c] for c in TEMPORO_PARIETAL if c in idx]
    with np.errstate(all="ignore"):
        # 비율 지표는 '채널별로 먼저 계산 → 좋은 채널끼리 평균'.
        # (채널마다 절대 파워 크기가 달라서, 깜빡임으로 AF 채널이 빠진 창과
        #  안 빠진 창의 값이 들쭉날쭉해지는 것을 막는다)
        th, al, be = bp["theta"], bp["alpha"], bp["beta"]
        out["log_engagement"] = np.nanmean(np.log(be / (al + th + EPS)), axis=1)  # Pope 1995
        # 피로: (θ+α)/(α+β) — Jap 2009 의 후보식 중 하나. (θ+α)/β 는 engagement 의 정확한 역수라
        # 정보가 중복되므로 쓰지 않는다.
        out["log_fatigue"] = np.nanmean(np.log((th + al) / (al + be + EPS)), axis=1)  # Jap 2009
        theta_f = np.nanmean(th[:, fr], axis=1) if fr else np.full(len(out), np.nan)
        alpha_p = np.nanmean(al[:, tp], axis=1) if tp else np.full(len(out), np.nan)
        out["theta_frontal"] = theta_f
        out["alpha_posterior"] = alpha_p
        out["log_workload"] = np.log(theta_f / (alpha_p + EPS))                    # Gevins 계열
        if "AF7" in idx and "AF8" in idx:
            out["faa"] = np.log(al[:, idx["AF8"]] + EPS) - np.log(al[:, idx["AF7"]] + EPS)
    for k in ("engagement", "fatigue", "workload"):
        out[k] = np.exp(out[f"log_{k}"])
    return out


def segment_spectrum(sess: Session, start: float, end: float, picks=None):
    """한 구간(예: 눈 감은 휴식 60초)의 평균 스펙트럼. 4초 세그먼트 → 0.25 Hz 해상도."""
    sf = sess.raw.info["sfreq"]
    x = sess.raw.get_data(picks=picks or "eeg", tmin=start, tmax=end) * 1e6
    nper = int(min(4 * sf, x.shape[1]))
    f, p = welch(x, fs=sf, nperseg=nper, noverlap=nper // 2, axis=-1, average="median")
    return f, p  # p: (n_ch, n_freq)


def individual_alpha_frequency(f: np.ndarray, p: np.ndarray) -> dict:
    """IAF: 알파 범위 안 최대 피크(peak)와 무게중심(CoG). p 는 1차원(채널 평균) 스펙트럼."""
    m = (f >= ALPHA_SEARCH[0]) & (f <= ALPHA_SEARCH[1])
    fa, pa = f[m], p[m]
    i = int(np.argmax(pa))
    peak = float(fa[i])
    if 0 < i < len(pa) - 1:  # 포물선 보간으로 해상도 보정
        y0, y1, y2 = np.log(pa[i - 1:i + 2])
        denom = y0 - 2 * y1 + y2
        if denom != 0:
            peak = float(fa[i] + 0.5 * (y0 - y2) / denom * (fa[1] - fa[0]))
    # 1/f 배경을 빼고 무게중심 계산
    slope = np.polyfit(np.log(f[(f > 2) & (f < 40)]), np.log(p[(f > 2) & (f < 40)]), 1)
    bg = np.exp(np.polyval(slope, np.log(fa)))
    resid = np.clip(pa - bg, 0, None)
    cog = float((fa * resid).sum() / resid.sum()) if resid.sum() > 0 else peak
    prominence = float(pa[i] / bg[i]) if bg[i] > 0 else np.nan
    return {"iaf_peak": round(peak, 2), "iaf_cog": round(cog, 2),
            "alpha_prominence": round(prominence, 2)}
