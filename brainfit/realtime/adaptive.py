"""활동 목록 · 반응도 판정 · 다음 활동 선택 · 활동별 피드백.

선택 규칙 (docs/LIVE_DEMO.md 4절)
  1) 처음 2개: 탐색 — 성향(brain_type)이 추천한 활동에 가중치를 둔 무작위, 서로 다른 영역
  2) 3번째부터: 직전 활동들에서 '목표 지표'(몰입/부하)의 반응이 약했으면
     → 그 지표를 더 강하게 끌어올리는 활동(자극 강도 arousal 높은 순)으로 보완
     반응이 충분했으면 → 아직 측정하지 않은 영역을 탐색
  3) 신호 품질이 나쁘면 '반응 없음'으로 오판하지 않고 '판단 보류' + 재착용 안내
"""
from __future__ import annotations

import random

import numpy as np
import pandas as pd

RESPONSIVE_Z = 0.8      # 임시 기준(휴식 대비 z). CogWear 검증 결과(Stroop 중 z 분포)로 보정할 것
MIN_WINDOWS = 6         # 판정에 필요한 최소 깨끗한 창 수(약 3초 분량 이상)
METRIC_KO = {"engagement": "몰입", "workload": "작업 부하", "fatigue": "피로"}

ACTIVITIES: dict[str, dict] = {
    "gonogo": {"name": "Go / No-Go", "domain": "억제조절", "targets": ["engagement"], "arousal": 2,
               "how": "초록 원이면 빠르게 누르고, 빨간 사각형이면 참기", "sec": 90},
    "nback": {"name": "위치 기억 (N-back)", "domain": "작업기억", "targets": ["workload", "engagement"],
              "arousal": 2, "how": "격자의 불빛 위치가 N번 전과 같으면 누르기", "sec": 90, "level": 2},
    "oddball": {"name": "드문 모양 찾기 (Oddball)", "domain": "주의 정확성", "targets": ["engagement"],
                "arousal": 1, "how": "동그라미 사이에 가끔 나오는 삼각형에만 반응", "sec": 90},
    "stroop": {"name": "색깔 단어 (Stroop)", "domain": "선택적 주의", "targets": ["engagement", "workload"],
               "arousal": 2, "how": "글자의 뜻이 아니라 글자 색을 고르기", "sec": 90},
    "arithmetic": {"name": "암산", "domain": "계산", "targets": ["workload", "engagement"], "arousal": 3,
                   "how": "제한 시간 안에 계산 결과 고르기 (점점 어려워짐)", "sec": 90},
    "pvt": {"name": "반응 속도 (PVT)", "domain": "각성·반응속도", "targets": ["engagement"], "arousal": 2,
            "how": "불규칙하게 나타나는 신호에 최대한 빨리 반응", "sec": 60},
    "word_memory": {"name": "단어 기억", "domain": "언어 기억", "targets": ["workload"], "arousal": 2,
                    "how": "단어 8개를 외운 뒤, 섞인 목록에서 본 단어 고르기", "sec": 90},
}


def task_name(activity: str, level: int | None = None) -> str:
    """분석 파이프라인과 맞춘 task 이름 (예: nback + level 2 → nback2)."""
    if activity == "nback":
        return f"nback{level or ACTIVITIES['nback']['level']}"
    return activity


def activity_of(task: str) -> str:
    return "nback" if str(task).startswith("nback") else str(task)


def summarize_activity(task, block, windows: pd.DataFrame, stats: dict | None, trials: list) -> dict:
    act = activity_of(task)
    res = {"task": task, "activity": act, "block": block, "name": ACTIVITIES.get(act, {}).get("name", task),
           "domain": ACTIVITIES.get(act, {}).get("domain"), "n_windows": int(len(windows))}
    if stats and len(windows) >= MIN_WINDOWS:
        z = {}
        for m in ("engagement", "workload", "fatigue"):
            mu, sd = stats[f"log_{m}"]
            v = (windows[f"log_{m}"] - mu) / sd
            z[m] = round(float(v.mean()), 2)
            if m == "engagement" and len(v) > 5:
                res["engagement_slope_per_min"] = round(float(np.polyfit(windows["t_in_phase"] / 60, v, 1)[0]), 2)
        res["z"] = z
        targets = ACTIVITIES.get(act, {}).get("targets", ["engagement"])
        best = max(targets, key=lambda m: z[m])
        res.update({"response": z[best], "response_metric": best, "responsive": z[best] >= RESPONSIVE_Z})
    else:
        res.update({"z": None, "response": None, "responsive": None,
                    "reason": "기준선이 없거나 깨끗한 데이터가 부족해 판단 보류"})
    if trials:
        t = pd.DataFrame([tr._asdict() if hasattr(tr, "_asdict") else tr for tr in trials])
        for c in ("target", "resp", "correct", "rt"):
            if c in t:
                t[c] = pd.to_numeric(t[c], errors="coerce")
        beh = {"n_trials": int(len(t)), "accuracy": round(float(t["correct"].mean()), 3)}
        if "target" in t and (t["target"] == 0).any():
            beh["fa_rate"] = round(float(((t["target"] == 0) & (t["resp"] == 1)).sum() / (t["target"] == 0).sum()), 3)
        if "target" in t and (t["target"] == 1).any():
            beh["miss_rate"] = round(float(((t["target"] == 1) & (t["resp"] == 0)).sum() / (t["target"] == 1).sum()), 3)
        rts = t.loc[(t.get("resp", 1) == 1) & (t["rt"] > 0), "rt"] if "rt" in t else pd.Series(dtype=float)
        if len(rts):
            beh["rt_median"] = round(float(rts.median()), 3)
            beh["rt_cv"] = round(float(rts.std() / rts.mean()), 3) if len(rts) > 2 else None
        res["behavior"] = beh
    res["feedback"] = feedback(res)
    return res


def josa(word: str, with_batchim: str, without: str) -> str:
    """한국어 조사 선택 (받침 유무). '로'는 ㄹ 받침에도 '로'."""
    ch = word.strip()[-1:] or "가"
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return without
    jong = code % 28
    if with_batchim == "으로" and jong == 8:  # ㄹ 받침
        return without
    return with_batchim if jong else without


def unresolved_weak(done: list[dict]) -> list[dict]:
    """반응이 약했던 활동 중, 이후 같은 지표를 끌어올린 활동이 아직 없는 것."""
    out = []
    for i, d in enumerate(done):
        if d.get("responsive") is not False:
            continue
        m = d["response_metric"]
        later = done[i + 1:]
        if not any(x.get("responsive") and (x.get("z") or {}).get(m, -9) >= RESPONSIVE_Z for x in later):
            out.append(d)
    return out


def choose_next(done: list[dict], n_total: int = 4, type_hint: dict | None = None,
                quality_ok: bool = True, seed: int | None = None, pool: list[str] | None = None) -> dict | None:
    rng = random.Random(seed)
    pool = pool or list(ACTIVITIES)
    if len(done) >= n_total:
        return None
    done_acts = [d["activity"] for d in done]
    remaining = [a for a in pool if a not in done_acts]
    if not remaining:
        return None

    def pick(act, reason, mode):
        lv = ACTIVITIES[act].get("level")
        return {"activity": act, "task": task_name(act, lv), "level": lv, "name": ACTIVITIES[act]["name"],
                "how": ACTIVITIES[act]["how"], "sec": ACTIVITIES[act]["sec"], "mode": mode, "reason": reason,
                "index": len(done) + 1, "total": n_total}

    if not quality_ok:
        act = rng.choice(remaining)
        return pick(act, "신호 품질이 낮아 뇌파 반응을 판단하기 어려워요. 착용을 확인한 뒤 다음 활동을 진행해요.", "hold")

    if len(done) < 2:  # 탐색 단계
        prefer = [a for a in (type_hint or {}).get("start_with", []) if a in remaining]
        used_domains = {ACTIVITIES[a]["domain"] for a in done_acts}
        cand = [a for a in remaining if ACTIVITIES[a]["domain"] not in used_domains] or remaining
        weights = [3 if a in prefer else 1 for a in cand]
        act = rng.choices(cand, weights=weights, k=1)[0]
        why = "오늘의 뇌파 성향에 맞춘 시작 활동이에요." if act in prefer else "여러 영역을 고르게 살펴보기 위한 탐색 활동이에요."
        return pick(act, why, "explore")

    weak = unresolved_weak(done)
    if weak:
        w = weak[-1]
        metric = w["response_metric"]
        cand = [a for a in remaining if metric in ACTIVITIES[a]["targets"]] or remaining
        cand.sort(key=lambda a: (ACTIVITIES[a]["arousal"], ACTIVITIES[a]["targets"][0] == metric,
                                 rng.random()), reverse=True)
        act = cand[0]
        nm = ACTIVITIES[act]["name"]
        reason = (f"'{w['name']}'에서는 {METRIC_KO[metric]} 반응이 약했어요(z={w['response']}). "
                  f"{METRIC_KO[metric]}{josa(METRIC_KO[metric], '을', '를')} 더 강하게 끌어올리는 "
                  f"'{nm}'{josa(nm, '으로', '로')} 이어갈게요.")
        return pick(act, reason, "compensate")
    covered = {ACTIVITIES[a]["domain"] for a in done_acts}
    cand = [a for a in remaining if ACTIVITIES[a]["domain"] not in covered] or remaining
    act = rng.choice(cand)
    return pick(act, f"앞 활동들에서 뇌파가 잘 반응했어요. 아직 살펴보지 않은 '{ACTIVITIES[act]['domain']}' 영역으로 넘어갈게요.", "explore")


TIPS = {
    "gonogo": [("fa_rate", ">", 0.25, "누르면 안 되는 신호에 반응한 비율이 높아요. 자극을 '확인하고 누르는' 0.2초 멈춤 습관을 연습해 보세요.")],
    "nback": [("accuracy", "<", 0.75, "위치 기억이 흔들렸어요. 위치를 '왼쪽 위'처럼 말로 붙여 기억하는 언어화 전략이 도움이 돼요.")],
    "oddball": [("miss_rate", ">", 0.2, "드문 모양을 놓친 경우가 있어요. 시선을 화면 중앙에 고정하고 '다름'에만 반응해 보세요.")],
    "stroop": [("accuracy", "<", 0.85, "글자 뜻에 끌려간 응답이 있어요. 글자를 읽기 전에 '색'부터 보는 연습을 해 보세요.")],
    "arithmetic": [("accuracy", "<", 0.7, "계산 중 실수가 늘었어요. 중간 결과를 속으로 한 번 되뇌고 넘어가 보세요.")],
    "pvt": [("rt_median", ">", 0.45, "반응이 다소 느려요. 짧은 스트레칭이나 휴식 뒤에 다시 해 보면 달라질 수 있어요.")],
    "word_memory": [("accuracy", "<", 0.75, "단어 기억이 아쉬웠어요. 단어들을 하나의 이야기로 엮거나 장면으로 떠올려 보세요.")],
}


def feedback(res: dict) -> list[str]:
    out = []
    beh = res.get("behavior", {})
    for key, op, thr, msg in TIPS.get(res.get("activity"), []):
        v = beh.get(key)
        if v is not None and ((op == ">" and v > thr) or (op == "<" and v < thr)):
            out.append(msg)
    z = res.get("z") or {}
    slope = res.get("engagement_slope_per_min")
    if slope is not None and slope < -0.5:
        out.append("활동 후반으로 갈수록 몰입이 떨어졌어요. 이런 활동은 짧게 나눠서(1~2분) 하는 게 좋아요.")
    if z.get("workload") is not None and z["workload"] > 2 and beh.get("accuracy", 1) < 0.7:
        out.append("뇌의 부담이 큰데 정확도가 낮아요. 난이도를 한 단계 낮춰 정확도를 먼저 올려 보세요.")
    if res.get("responsive") is False:
        out.append("이 활동에서는 뇌파 변화가 작았어요. 너무 쉬웠거나 몰입이 덜 됐을 수 있어요.")
    if res.get("responsive") and not out:
        out.append("뇌파와 수행 모두 안정적이었어요. 이 활동은 지금 수준을 유지해도 좋아요.")
    return out
