"""BrainFit 전역 설정.

여기 있는 숫자는 '문헌 기반 출발값'이다. 파일럿 측정 후 팀이 합의해서 바꾸고,
바꾼 이유는 docs/METRICS.md 의 '변경 이력'에 남긴다.
"""
from dataclasses import dataclass

# ── Muse 2 (BlueMuse → LSL) ──────────────────────────────────────────
MUSE_EEG_CHANNELS = ["TP9", "AF7", "AF8", "TP10"]  # Right AUX 는 사용하지 않음
MUSE_AUX_CHANNELS = ["Right AUX"]
FRONTAL = ["AF7", "AF8"]      # 이마: 세타/작업부하, 단 눈 깜빡임에 취약
TEMPORO_PARIETAL = ["TP9", "TP10"]  # 귀 뒤: 알파(안정/눈감기 반응)가 잘 보임
MUSE_SFREQ = 256.0
LINE_FREQ = 60.0  # 한국 전원 주파수

# ── 주파수 대역 (Hz) ─────────────────────────────────────────────────
BANDS: dict[str, tuple[float, float]] = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 40.0),  # Muse 건식 전극에선 근전도(EMG) 오염이 커서 해석에 쓰지 않음
}
ALPHA_SEARCH = (7.0, 13.0)  # IAF(개인 알파 피크) 탐색 범위


@dataclass
class PreprocessConfig:
    l_freq: float = 1.0
    h_freq: float = 40.0
    notch: float | None = LINE_FREQ
    win_sec: float = 2.0       # 분석 창 길이
    step_sec: float = 0.5      # 창 이동 간격 (0.25 면 더 촘촘하지만 4배 느림)
    ptp_reject_uv: float = 150.0  # 창 안 최대-최소 진폭이 이보다 크면 잡음(깜빡임/움직임)
    flat_uv: float = 0.5          # 표준편차가 이보다 작으면 접촉 불량(평탄)
    min_good_channels: int = 2    # 이 수 미만이면 그 창 전체를 버림


@dataclass
class CognitiveConfig:
    smooth_sec: float = 20.0         # 집중 곡선 평활 창
    drop_z: float = -1.0             # 기준 대비 이 z 아래로 떨어지면 '집중 저하'
    drop_hold_sec: float = 30.0      # 저하가 이 시간 이상 지속돼야 '이탈'로 인정
    early_ref_sec: float = 120.0     # 과제 초반 몇 초를 '과제 중 기준'으로 쓸지
    min_history_sessions: int = 3    # 개인 기준선을 쓰려면 최소 세션 수


PRE = PreprocessConfig()
COG = CognitiveConfig()


# ── BrainFit Cognitive Battery 모드 (docs/BATTERY.md) ────────────────
# 시간 단위: 초. iti 는 (최소, 최대) 균등분포 지터 → 리듬 예측(기대 반응) 방지
BATTERY_MODES: dict[str, dict] = {
    "standard": {  # 성인·학생, 약 15분
        "rest_sec": 60, "between": 15, "post_rest": True, "pvt": None,
        "gonogo": {"n": 100, "p_nogo": 0.25, "stim": 0.30, "window": 0.80, "iti": (0.7, 1.1)},
        "nback": {"levels": [1, 2, 2, 1], "trials": 20, "stim": 0.50, "trial": 2.5},
        "oddball": {"n": 180, "p_target": 0.20, "stim": 0.25, "iti": (1.0, 1.3)},
    },
    "senior": {  # 노년층, 약 15분: 느린 속도·큰 자극·쉬운 단계, PVT 포함
        "rest_sec": 60, "between": 20, "post_rest": True,
        "pvt": {"sec": 90, "isi": (2.0, 6.0), "timeout": 1.5},
        "gonogo": {"n": 80, "p_nogo": 0.25, "stim": 0.50, "window": 1.20, "iti": (1.0, 1.4)},
        "nback": {"levels": [0, 1, 2, 1], "trials": 16, "stim": 0.80, "trial": 3.0},
        "oddball": {"n": 150, "p_target": 0.20, "stim": 0.40, "iti": (1.1, 1.4)},
    },
    "demo": {  # 무대 시연, 약 6분 (P300 은 미리 녹화한 세션으로 보여줄 것)
        "rest_sec": 30, "between": 5, "post_rest": False, "pvt": None,
        "gonogo": {"n": 40, "p_nogo": 0.25, "stim": 0.30, "window": 0.80, "iti": (0.7, 1.1)},
        "nback": {"levels": [1, 2], "trials": 12, "stim": 0.50, "trial": 2.5},
        "oddball": {"n": 80, "p_target": 0.20, "stim": 0.25, "iti": (1.0, 1.3)},
    },
}

# ── 육각형 Brain Profile: 축 정의와 '임시' 기준값 ──────────────────────
# ⚠️ 아래 mean/sd 는 근거 있는 규준이 아니라 출발용 임시값이다.
#    파일럿(연령대별 최소 5명) 측정 후 실제 평균·SD 로 반드시 교체하고 docs/METRICS.md 에 기록.
#    higher_better=False 면 값이 작을수록 좋은 지표(반응시간, 오반응률 등).
HEX_AXES: dict[str, dict] = {
    "speed":      {"ko": "반응속도",  "metric": "gonogo_rt_median", "higher_better": False},
    "inhibition": {"ko": "억제조절",  "metric": "gonogo_commission", "higher_better": False},
    "wm":         {"ko": "작업기억",  "metric": "nback2_dprime", "higher_better": True},
    "attention":  {"ko": "주의 정확성", "metric": "oddball_dprime", "higher_better": True},
    "sustain":    {"ko": "집중 유지",  "metric": "sustain_composite", "higher_better": True},
    "p300":       {"ko": "뇌 반응(P300)", "metric": "p300_amp_uv", "higher_better": True},
}
HEX_REFERENCE: dict[str, dict[str, tuple[float, float]]] = {
    "adult": {"gonogo_rt_median": (0.38, 0.06), "gonogo_commission": (0.15, 0.10),
              "nback2_dprime": (2.0, 0.9), "oddball_dprime": (3.5, 0.8),
              "sustain_composite": (0.5, 0.2), "p300_amp_uv": (4.0, 3.0)},
    "senior": {"gonogo_rt_median": (0.50, 0.09), "gonogo_commission": (0.20, 0.12),
               "nback2_dprime": (1.3, 0.8), "oddball_dprime": (3.0, 0.9),
               "sustain_composite": (0.5, 0.2), "p300_amp_uv": (3.0, 3.0)},
}
ERP_MIN_TARGET_EPOCHS = 25   # 깨끗한 타깃 에포크가 이보다 적으면 P300 축은 '측정 불충분'
