"""잡음 구간 표시(마스크). 오프라인(preprocess)과 실시간(engine)이 같은 규칙을 쓴다.

Muse 의 이마 채널(AF7/AF8)은 눈 바로 위라서 눈을 뜨고 있으면 깜빡임·눈 움직임이 1분에 15~20번씩
100~300 µV 파형으로 들어온다. 예전에는 2초 창 안에 한 번만 있어도 창 전체를 버려서
눈 뜬 상태의 이마 채널이 거의 다 버려졌다. 이제는 깜빡임 부분(앞뒤 0.25초 포함)만 가린다.
"""
from __future__ import annotations

import numpy as np

from .config import FRONTAL, PRE, PreprocessConfig


def artifact_mask(x_uv: np.ndarray, ch_names: list[str], sfreq: float,
                  cfg: PreprocessConfig = PRE) -> np.ndarray:
    """x_uv: (n_ch, n) 필터된 µV 신호 → (n_ch, n) bool, True = 가린 샘플.
    깜빡임은 양쪽 이마에 동시에 나타나므로 두 이마 채널의 합집합을 둘 다에 적용한다.
    귀 뒤 채널(TP9/TP10)은 가리지 않는다(거기서 큰 진폭은 접촉 불량·근육 → 창 단위로 버림)."""
    mask = np.zeros(x_uv.shape, dtype=bool)
    fr = [i for i, c in enumerate(ch_names) if c in FRONTAL]
    if not fr or x_uv.shape[1] == 0:
        return mask
    hit = (np.abs(x_uv[fr]) > cfg.blink_uv).any(axis=0)
    pad = int(round(cfg.blink_pad_sec * sfreq))
    if pad and hit.any():
        hit = np.convolve(hit.astype(float), np.ones(2 * pad + 1), mode="same") > 0
    mask[fr] = hit
    return mask


def rising_edges(row: np.ndarray) -> np.ndarray:
    """가림 구간이 시작되는 위치(인덱스)들 = 깜빡임 이벤트."""
    r = row.astype(np.int8)
    return np.flatnonzero(np.diff(np.concatenate([[0], r])) == 1)


def clean_segment_count(mask_win: np.ndarray, nper: int) -> np.ndarray:
    """mask_win: (..., n_samp) → 가림 없는 1초 조각(0.25초 간격) 수 (...,)"""
    n = mask_win.shape[-1]
    starts = range(0, n - nper + 1, nper // 4)
    return np.stack([~mask_win[..., s:s + nper].any(-1) for s in starts], axis=-1).sum(-1)
