"""[4번 연결] 규칙 기반 훈련 추천 + 적응형 난이도.

'AI 추천'은 처음엔 설명 가능한 규칙으로 시작하고, 데이터가 쌓이면
(사용자, 훈련, 다음 세션 점수 변화) 기록으로 밴딧/회귀 모델로 바꾼다.
"""
from __future__ import annotations

TRAINING = {
    "speed": ("반응속도 훈련", "PVT·빠른 반응 게임 5분, 자극 간격을 점점 짧게"),
    "inhibition": ("억제조절 훈련", "Go/No-Go·Stroop 5분, No-Go 비율 25→35%"),
    "wm": ("작업기억 훈련", "적응형 Grid N-back 8분 (아래 규칙으로 N 자동 조절)"),
    "attention": ("주의 정확성 훈련", "Oddball·Flanker 변형 5분, 방해 자극 추가"),
    "sustain": ("집중 유지 훈련", "몰입 지표 피드백(게이지) 켜고 10분 연속 과제, 매주 1분씩 연장"),
    "p300": ("주의 반응 훈련", "Oddball 과제 반복 (P300 은 참고 지표로만 추적)"),
}


def recommend(profile: dict, history_scores: dict | None = None, k: int = 2) -> list[dict]:
    """가장 낮은 축 k 개 추천. 본인 평균 대비 10점 이상 떨어진 축은 우선."""
    items = []
    for key, ax in profile["axes"].items():
        if ax["score"] is None:
            continue
        drop = 0
        if history_scores and history_scores.get(key) is not None:
            drop = history_scores[key] - ax["score"]
        items.append((ax["score"] - (20 if drop >= 10 else 0), key, ax, drop))
    items.sort()
    out = []
    for _, key, ax, drop in items[:k]:
        name, how = TRAINING[key]
        why = f"{ax['ko']} {ax['score']}점" + (f" (평소보다 {drop:.0f}점 낮음)" if drop >= 10 else "")
        out.append({"axis": key, "training": name, "how": how, "why": why})
    return out


def next_nback_level(n: int, accuracy: float, workload_z: float | None = None) -> int:
    """적응형 N-back: 정확도 ≥85% 이고 뇌 부하가 과도하지 않으면 +1, 60% 미만이거나
    부하 z > 2 인데 정확도도 75% 미만이면 −1. (Jaeggi 2008 의 적응 규칙을 단순화)"""
    if accuracy >= 0.85 and (workload_z is None or workload_z < 1.5):
        return n + 1
    if accuracy < 0.60 or (workload_z is not None and workload_z > 2.0 and accuracy < 0.75):
        return max(1, n - 1)
    return n
