"""공개 데이터셋 목록 — docs/DATASETS.md 와 scripts/download_datasets.py 가 이 표를 쓴다."""

REGISTRY: dict[str, dict] = {
    "cogwear": {
        "title": "CogWear: cognitive effort with consumer-grade wearables",
        "device": "Muse S (TP9/AF7/AF8/TP10, 256 Hz, Mind Monitor CSV)",
        "content": "휴식 3분 vs Stroop, 파일럿 11명 + 게이미피케이션 13명(2세션)",
        "use": "휴식 대비 인지부하에서 engagement/workload 지표 검증, LOSO 분류",
        "url": "https://physionet.org/content/consumer-grade-wearables/1.0.0/",
        "zip": "https://physionet.org/content/consumer-grade-wearables/get-zip/1.0.0/",
        "size": "ZIP 약 179 MB (압축 해제 약 2.7 GB)",
        "license": "ODbL v1.0 (PhysioNet open)",
        "cite": "Grzeszczyk et al. (2023) CogWear, PhysioNet, doi:10.13026/5f6t-b637",
        "local": "data/external/cogwear",
    },
    "muse_n400": {
        "title": "Muse 2 N400 semantic relatedness (37 subjects)",
        "device": "Muse 2 via BlueMuse + LSL → LabRecorder .xdf (우리와 동일)",
        "content": "단어쌍 관련/무관 112시행(56/56), PsychoPy 마커, 행동 데이터",
        "use": "load_xdf·ERP 코드를 실제 Muse 녹화로 검증, 언어 축 ERP 근거",
        "url": "https://osf.io/u6y9g/",
        "zip": "https://files.osf.io/v1/resources/u6y9g/providers/osfstorage/?zip=",
        "size": "확인 필요 (EEG Data/Raw EEG 의 .xdf 만 받으면 충분)",
        "license": "OSF 페이지의 라이선스 확인 후 사용",
        "cite": "Hayes & Magne (2025) Data in Brief; Hayes & Magne (2024) Sensors 24:7961",
        "local": "data/external/muse_n400",
    },
}
