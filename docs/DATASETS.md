# 공개 데이터셋

> 원본은 `data/external/<이름>/` 에 두고 **커밋하지 않는다**(.gitignore). 목록의 단일 출처는 `brainfit/datasets/registry.py`.
> Muse 가 아닌 데이터는 전극·기준전극이 달라 **절대값 비교 금지** — 방법 검증, 연령대 참고 분포, 사전학습 용도로만.

## 지금 구현된 것 (Muse 데이터)

| 이름 | 내용 | 로더 / 검증 스크립트 |
|---|---|---|
| `cogwear` | PhysioNet CogWear — Muse S(Mind Monitor CSV), 휴식 3분 vs Stroop, 파일럿 11명 + 13명×2세션, Stroop 응답 포함. ZIP 약 179 MB, ODbL | `brainfit/datasets/cogwear.py` / `scripts/validate_cogwear.py` |
| `muse_n400` | OSF u6y9g — Muse 2 + BlueMuse + LSL → LabRecorder .xdf (우리와 동일), 37명, 관련/무관 단어쌍 56/56 | `brainfit/datasets/muse_n400.py` / `scripts/validate_muse_n400.py` |

### 사용 순서
```bash
python scripts/download_datasets.py --list
python scripts/download_datasets.py --dataset cogwear
python scripts/validate_cogwear.py --root data/external/cogwear          # → outputs/validation/cogwear/

python scripts/download_datasets.py --dataset muse_n400                  # 실패 시 안내대로 .xdf 만 수동 다운로드
python scripts/validate_muse_n400.py --inspect data/external/muse_n400/<파일>.xdf   # 마커 패턴 확인
python scripts/validate_muse_n400.py --root data/external/muse_n400 --target-filter "<목표단어 마커 정규식>"
```

### 각 검증이 확인하는 것
**CogWear** — ① Stroop 중 engagement·workload z 가 본인 휴식보다 높은가(사람 단위 Wilcoxon) ② 과제 중 알파↓·베타↑ ③ 휴식/과제 분류에서 '개인 정규화'가 LOSO 정확도를 올리는가 ④ Stroop 간섭효과(불일치 RT − 일치 RT).
주의: 실험 순서가 Stroop → 휴식이라 휴식 구간에 과제 여운이 섞일 수 있다. Mind Monitor 의 `time` 열은 묶음 단위로 찍혀 샘플 간격으로 쓰지 않는다(행 순서 = 256 Hz 샘플 순서로 처리, 실효 샘플링률만 점검).

**Muse N400** — ① `load_xdf` 가 실제 BlueMuse 녹화를 읽는가(채널·샘플링률·끊김·마커) ② 잡음 제외 후 조건별 시행이 원 논문 기준(관련 24, 무관 27) 이상 남는가 ③ 300–500 ms 무관−관련 차이가 음(−)인가(원 논문: AF8 에서 유의).
주의: PsychoPy 마커 문자열 형식은 파일을 열어 봐야 안다 → 반드시 `--inspect` 먼저.

> 테스트(`tests/test_datasets.py`)는 실제 파일 형식을 흉내 낸 가짜 데이터로 **연결 상태만** 확인한다. 가짜 데이터의 결과 수치(분류 정확도 1.0 등)는 의미가 없다.

## 다음 후보 (로더 미구현)

| 데이터 | 기기/규모 | 용도 |
|---|---|---|
| MPI-LEMON | 62채널, 청년 153 / 노년 74명, EO·EC 휴식, AWS S3 | 연령대별 IAF·알파 반응성 참고 분포 (`POPULATION_REF`) |
| OpenNeuro ds004504 (+ds006036) | 19채널 임상, 눈 감은 휴식, AD 36 / FTD 23 / 건강 29명(평균 약 68세) | **건강 노년 참고용만**. 치매 분류기 제작 금지(진단 주장) |
| PhysioNet EEG Motor Movement/Imagery | 64채널, 109명, run1 EO / run2 EC | 알파 반응성 코드 빠른 검증 (`mne.datasets.eegbci`) |
| COG-BCI (Zenodo) | 64채널, 29명 × 3세션, N-back·PVT·Flanker·MATB, BIDS | 재검사 신뢰도 r 추정 → RCI |
| ERP CORE | 연구용, 40명, P3 oddball·N400·Flanker ERN, CC BY-SA 4.0 | P300 파이프라인 검증 |
| PhysioNet EEGMAT | 23채널, 36명, 눈감기 휴식 vs 연속 뺄셈 | 계산 과제·workload |
| STEW (IEEE DataPort) | Emotiv 14채널, 48명, 휴식 vs 멀티태스킹 + 주관 부하 1–9 | 주관 부하와 지표 관계 |
| Mental Attention State (Kaggle) | Emotiv, 5명 25시간, 집중/비집중/졸림 | 5번 집중 모드: 장시간 저하·졸림 |
| Bird 2018 mental state (Kaggle) | Muse, 5명 × 3상태 × 1분, **특징값으로 가공됨** | 분류 데모용 |

## 원칙
1. 같은 기기(Muse) 데이터 먼저.
2. 통계·평가는 **사람 단위** (창 단위 p-value 금지, LOSO 교차검증).
3. 주력 모델은 개인 보정 모델. 공개 데이터는 사전학습·참고.
4. 각 데이터의 라이선스·인용을 README/발표 자료에 표기.
