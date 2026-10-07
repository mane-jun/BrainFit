"""전처리: 필터 → 창 나누기 → 잡음 창 표시.

Muse 는 채널이 4개뿐이라 ICA 같은 고급 잡음 제거가 사실상 불가능하다.
그래서 (1) 이마 채널의 눈 깜빡임은 그 부분만 가리고(artifacts.py),
(2) 그래도 진폭이 큰 창·채널은 버린다(reject). 버린 비율은 품질 지표로 보고한다.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .artifacts import artifact_mask, clean_segment_count
from .config import FRONTAL, PRE, PreprocessConfig
from .io import Session


def filter_session(sess: Session, cfg: PreprocessConfig = PRE) -> Session:
    raw = sess.raw.copy().load_data()
    if cfg.notch:
        raw.notch_filter(cfg.notch, verbose=False)
    raw.filter(cfg.l_freq, cfg.h_freq, fir_design="firwin", verbose=False)
    return Session(raw=raw, events=sess.events, meta=dict(sess.meta, filtered=True))


def make_windows(sess: Session, cfg: PreprocessConfig = PRE, return_masks: bool = False):
    """연속 신호를 겹치는 창으로 자른다.

    반환:
      win: (n_win, n_ch, n_samp) 볼트 단위
      info: DataFrame[t_start, t_center, good_<ch>..., n_good, good, masked_frontal]
      (return_masks=True 면) masks: (n_win, n_ch, n_samp) True=깜빡임으로 가린 샘플
    채널 판정: 가린 샘플을 뺀 나머지의 진폭(ptp)이 기준 이하 + 평탄하지 않음 + 깨끗한 1초 조각 ≥ 1
    """
    x = sess.raw.get_data(picks="eeg")  # Right AUX 등은 자동 제외
    sf = sess.raw.info["sfreq"]
    w, s = int(cfg.win_sec * sf), int(cfg.step_sec * sf)
    win = sliding_window_view(x, w, axis=1)[:, ::s, :].transpose(1, 0, 2)
    t_start = np.arange(win.shape[0]) * s / sf

    mask = artifact_mask(x * 1e6, sess.raw.ch_names, sf, cfg)
    wmask = sliding_window_view(mask, w, axis=1)[:, ::s, :].transpose(1, 0, 2)
    uv = np.where(wmask, np.nan, win * 1e6)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ptp = np.nanmax(uv, axis=2) - np.nanmin(uv, axis=2)
        sd = np.nanstd(uv, axis=2)
    nclean = clean_segment_count(wmask, min(w, int(sf)))
    good_ch = (ptp < cfg.ptp_reject_uv) & (sd > cfg.flat_uv) & (nclean >= 1)

    info = pd.DataFrame({"t_start": t_start, "t_center": t_start + cfg.win_sec / 2})
    for ci, ch in enumerate(sess.raw.ch_names):
        info[f"good_{ch}"] = good_ch[:, ci]
    info["n_good"] = good_ch.sum(axis=1)
    info["good"] = info["n_good"] >= cfg.min_good_channels
    fr = [i for i, c in enumerate(sess.raw.ch_names) if c in FRONTAL]
    info["masked_frontal"] = wmask[:, fr, :].mean(axis=(1, 2)) if fr else 0.0
    if return_masks:
        return win, info, wmask
    return win, info


def label_windows(info: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """창 중심 시각이 어느 구간(rest_eo / rest_ec / block ...)에 속하는지 붙인다."""
    info = info.copy()
    info["segment"] = "other"
    info["task"] = None
    info["block"] = np.nan
    info["t_in_segment"] = np.nan
    # 긴 구간부터 칠해서 짧은(구체적인) 구간이 덮어쓰게 한다. 'session' 전체 구간은 제외.
    segs = segments[segments["name"] != "session"].sort_values("duration", ascending=False)
    for _, sg in segs.iterrows():
        m = (info["t_center"] >= sg["start"]) & (info["t_center"] < sg["end"])
        info.loc[m, "segment"] = sg["name"]
        info.loc[m, "task"] = sg["task"]
        info.loc[m, "block"] = sg["block"]
        info.loc[m, "t_in_segment"] = info.loc[m, "t_center"] - sg["start"]
    return info


def quality_report(info: pd.DataFrame, ch_names: list[str]) -> dict:
    rep = {"good_window_ratio": round(float(info["good"].mean()), 3)}
    for ch in ch_names:
        rep[f"{ch}_good_ratio"] = round(float(info[f"good_{ch}"].mean()), 3)
    by_seg = info.groupby("segment")["good"].mean().round(3).to_dict() if "segment" in info else {}
    rep["by_segment"] = by_seg
    rep["usable"] = rep["good_window_ratio"] >= 0.6
    return rep
