"""'오늘의 뇌파 성향' 분류 — 눈 뜬/감은 휴식(1번 기준선)으로 판단.

⚠️ 이것은 성격·능력·진단이 아니라 '지금 상태의 경향'이다. 같은 사람도 날마다 바뀔 수 있다.
⚠️ POP_REF 는 임시 참고값이다. scripts/build_population_ref.py(예정)로 LEMON 등에서 계산해 교체한다.
"""
from __future__ import annotations

# 눈 뜬 휴식의 상대 파워(1–40 Hz 대비) 임시 참고 분포 (평균, SD)
POP_REF = {"theta": (0.18, 0.06), "alpha": (0.25, 0.10), "beta": (0.20, 0.07)}
DOMINANCE_Z = 0.5

TYPES = {
    "relaxed": {
        "name": "안정·이완형",
        "summary": "휴식 중 알파 리듬이 뚜렷해요. 마음이 차분한 상태로 시작했어요.",
        "start_with": ["pvt", "gonogo", "arithmetic"],
        "tip": "몸을 깨우는 빠른 반응 활동부터 시작하면 몰입으로 넘어가기 쉬워요.",
    },
    "alert": {
        "name": "각성·긴장형",
        "summary": "휴식 중에도 베타 리듬 비중이 높아요. 이미 머리가 바쁘게 돌아가는 상태예요.",
        "start_with": ["oddball", "nback", "word_memory"],
        "tip": "처음 1분은 천천히 호흡하고, 정확도가 중요한 활동부터 해 보세요.",
    },
    "low_arousal": {
        "name": "저각성형(졸림 경향)",
        "summary": "휴식 중 세타 리듬 비중이 높아요. 다소 졸리거나 피곤한 상태일 수 있어요.",
        "start_with": ["pvt", "gonogo", "stroop"],
        "tip": "짧고 빠른 활동으로 각성을 먼저 올리고, 어려운 활동은 뒤에 배치해요.",
    },
    "balanced": {
        "name": "균형형",
        "summary": "세타·알파·베타가 고르게 나타나요. 무난한 출발 상태예요.",
        "start_with": ["nback", "stroop", "arithmetic"],
        "tip": "작업기억처럼 집중이 필요한 활동부터 바로 시작해도 좋아요.",
    },
}


def classify(baseline: dict) -> dict:
    rel = baseline.get("rel_eo")
    if not rel:
        return {"id": "unknown", "name": "판단 보류",
                "summary": baseline.get("warning", "기준선 데이터가 부족해 판단하지 못했어요."),
                "evidence": {}, "notes": [], "start_with": [], "tip": "착용 상태를 확인하고 다시 측정해 주세요."}
    z = {b: (rel[b] - m) / s for b, (m, s) in POP_REF.items()}
    top = max(z, key=z.get)
    tid = {"alpha": "relaxed", "beta": "alert", "theta": "low_arousal"}[top] if z[top] >= DOMINANCE_Z else "balanced"
    t = TYPES[tid]
    notes = []
    react = baseline.get("alpha_reactivity")
    if react is not None and react < 1.3:
        notes.append("눈을 감아도 알파가 크게 늘지 않았어요. 귀 뒤 센서 접촉을 확인하거나, 긴장 상태일 수 있어요.")
    iaf = baseline.get("iaf_peak")
    if iaf is not None:
        notes.append(f"고유 알파 리듬 {iaf:.1f} Hz" + (" (느린 편)" if iaf < 9 else " (빠른 편)" if iaf > 11 else ""))
    return {"id": tid, "name": t["name"], "summary": t["summary"], "tip": t["tip"],
            "start_with": t["start_with"], "notes": notes,
            "evidence": {"rel_eo": {k: round(v, 3) for k, v in rel.items()},
                         "z_vs_reference": {k: round(v, 2) for k, v in z.items()},
                         "alpha_reactivity": react, "iaf_peak": iaf},
            "disclaimer": "오늘의 뇌파 성향이며 성격·능력·진단이 아닙니다. 참고값은 임시 기준입니다."}
