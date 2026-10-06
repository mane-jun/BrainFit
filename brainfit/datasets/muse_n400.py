"""Muse 2 N400 데이터셋 (Hayes & Magne, OSF u6y9g) — LabRecorder .xdf 로더.

이 데이터는 우리와 같은 BlueMuse → LSL → LabRecorder 경로로 녹화돼 있어
brainfit.io.load_xdf 를 '실제 Muse 파일'로 검증하는 데 가장 적합하다.

⚠️ PsychoPy 마커 문자열의 정확한 형식은 파일을 열어 봐야 안다.
   1) python scripts/validate_muse_n400.py --inspect <파일.xdf>  로 마커 종류·개수를 확인
   2) 관련/무관 '목표 단어' 마커를 고르는 정규식을 --related / --unrelated 로 지정
   기본 정규식은 흔한 표기(related/unrelated, rel/unrel)를 가정한 추측값이다.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import numpy as np

from ..io import Session, load_xdf

DEFAULT_RELATED = r"(?i)related|\brel\b|_rel\b|congruent|match"  # unrelated 를 먼저 검사하므로 안전
DEFAULT_UNRELATED = r"(?i)unrelated|\bunrel\b|_unrel\b|incongruent|mismatch"


def find_xdf(root: str | Path) -> list[Path]:
    return sorted(Path(root).rglob("*.xdf"))


def marker_counts(sess: Session, collapse_digits: bool = True) -> Counter:
    """마커 문자열 종류별 개수. collapse_digits=True 면 숫자를 #로 바꿔 '패턴' 단위로 센다
    (예: target_unrelated_12 → target_unrelated_#)."""
    if "raw" not in sess.events:
        return Counter()
    txt = sess.events["raw"].astype(str)
    if collapse_digits:
        txt = txt.str.replace(r"\d+", "#", regex=True)
    return Counter(txt)


def condition_onsets(sess: Session, related: str = DEFAULT_RELATED,
                     unrelated: str = DEFAULT_UNRELATED, target_filter: str | None = None
                     ) -> dict[str, np.ndarray]:
    """마커 문자열을 정규식으로 분류해 조건별 시점(초)을 돌려준다.
    unrelated 를 먼저 검사한다('unrelated' 안에 'related' 가 들어 있으므로)."""
    ev = sess.events
    rel_on, unrel_on = [], []
    for _, r in ev.iterrows():
        txt = str(r.get("raw", ""))
        if target_filter and not re.search(target_filter, txt):
            continue
        if re.search(unrelated, txt):
            unrel_on.append(r["onset"])
        elif re.search(related, txt):
            rel_on.append(r["onset"])
    return {"related": np.array(rel_on), "unrelated": np.array(unrel_on)}


def load(path: str | Path) -> Session:
    sess = load_xdf(path)
    sess.meta["dataset"] = "muse_n400"
    sess.meta["participant"] = Path(path).stem
    return sess
