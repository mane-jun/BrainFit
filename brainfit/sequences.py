"""과제 자극 순서 생성기 — 과제 앱(tasks/)과 가짜 데이터(synth)가 같은 규칙을 쓰도록 공유."""
from __future__ import annotations

import random


def spaced_rare_sequence(n: int, p_rare: float, rng: random.Random, min_gap: int = 2) -> list[int]:
    """드문 자극(0 또는 타깃)이 연속되지 않고 앞에 흔한 자극이 min_gap 개 이상 오도록 배치.

    반환: 1 = 흔한 자극, 0 = 드문 자극 (Go/No-Go 에서는 1=Go, 0=No-Go)
    """
    n_rare = round(n * p_rare)
    units = [[1] * min_gap + [0] for _ in range(n_rare)]
    rest = n - n_rare * (min_gap + 1)
    if rest < 0:
        raise ValueError("p_rare 가 너무 커서 간격 조건을 만족할 수 없습니다.")
    units += [[1] for _ in range(rest)]
    rng.shuffle(units)
    return [x for u in units for x in u]


def gonogo_sequence(n: int, p_nogo: float, rng: random.Random) -> list[int]:
    """1 = Go(눌러야 함), 0 = No-Go(누르면 안 됨)"""
    return spaced_rare_sequence(n, p_nogo, rng)


def oddball_sequence(n: int, p_target: float, rng: random.Random) -> list[int]:
    """1 = 타깃(드문 △, 눌러야 함), 0 = 표준(○)"""
    return [1 - x for x in spaced_rare_sequence(n, p_target, rng)]
