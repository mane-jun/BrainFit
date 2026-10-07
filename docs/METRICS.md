# 지표 정의와 근거

> 숫자 임계값은 모두 `brainfit/config.py` 에 있다. 바꾸면 아래 '변경 이력'에 날짜·이유를 남긴다.
> 참고문헌은 기획안·발표에 인용하기 전에 **원문을 직접 확인**한다(서지 정보 오기 방지).

## 0. 공통 처리
| 단계 | 방법 | 이유 |
|---|---|---|
| 필터 | 60 Hz 노치 + 1–40 Hz 대역통과 (연속 신호 전체) | 드리프트·전원잡음·근전도 감소 |
| 창 | 2초 창, 0.5초 간격 | 2초 → 주파수 해상도 확보, 0.5초 → 시간 해상도 |
| 눈 깜빡임 | 이마 채널(AF7/AF8)에서 \|신호\| > 100 µV 인 부분 + 앞뒤 0.25초만 가림(두 채널 공통). 대역 파워는 가려지지 않은 1초 조각들로 계산 | 눈 뜬 상태에서 이마 채널을 통째로 버리지 않기 위해 (artifacts.py) |
| 잡음 제거 | 가린 부분을 뺀 나머지에서 ptp > 150 µV 또는 SD < 0.5 µV, 또는 깨끗한 1초 조각이 없으면 그 채널 제외. 좋은 채널 < 2 개면 창 제외 | 4채널이라 ICA 불가 → 가림 + reject 전략 |
| 스펙트럼 | Welch (창 안 1초 세그먼트 50% 겹침), µV²/Hz | 표준 PSD 추정 |
| 대역 파워 | 대역 적분, 비율 지표는 채널별 계산 → 좋은 채널 평균 | 채널 탈락에 강건 |
| 정규화 | 같은 세션 EO 휴식의 평균·SD 로 z 점수 | 개인차·착용 상태 차이 제거 |

## 1. 기준선 지표 (세부내용 1번)
| 지표 | 식 | 의미 | 근거 |
|---|---|---|---|
| 알파 반응성 | α(EC) / α(EO), TP9·TP10 | 눈 감으면 알파↑ (Berger 효과). **측정이 정상인지 확인하는 1차 지표**이자 각성 상태 지표 | Barry et al., 2007 |
| IAF (개인 알파 피크) | EC 스펙트럼 7–13 Hz 최대값(포물선 보간) + 1/f 제거 후 무게중심 | 개인 고유 특성, 인지 수행과 관련 보고. 개인 맞춤 대역 설정에 사용 | Klimesch, 1999; Corcoran et al., 2018 |
| 상대 파워 | 대역 / 전체(1–40 Hz) | 장비·접촉 상태 영향을 줄인 대역 구성비 | – |
| (확장) 비주기 기울기 | specparam(FOOOF)의 aperiodic exponent | 1/f 기울기, 연령·각성 관련 보고 | Donoghue et al., 2020 |

**개인 기준선 누적**: `BaselineStore` 가 세션마다 IAF, 알파 반응성, 집중 점수를 저장. 이력 3회 이상이면 '나의 평소' 평균·SD 로 오늘 z 를 계산, 미만이면 집단 참고값(문헌/공개 데이터)으로 대체하고 그 사실을 표시.

## 2. 상태 지표 (세부내용 3번)
| 지표 | 식 | 해석 | 근거 |
|---|---|---|---|
| Engagement (몰입) | log[ β / (α + θ) ] | ↑ = 과제 몰입·각성 | Pope et al., 1995 (NASA 엔게이지먼트 지수) |
| Workload (작업 부하) | log[ θ(AF7,AF8) / α(TP9,TP10) ] | ↑ = 작업기억 부하. N 이 클수록 ↑ 기대 | Gevins et al., 1997; Jensen & Tesche, 2002 |
| Fatigue (피로) | log[ (θ + α) / (α + β) ] | 시간 경과에 따라 ↑ | Jap et al., 2009; Wascher et al., 2014 |
| FAA (선택) | ln α(AF8) − ln α(AF7) | 접근/회피 동기 관련, 이 프로젝트에선 참고만 | Coan & Allen, 2004 |

> Muse 에는 Fz(전두 정중선)가 없어 AF7/AF8 이 대용이다. AF 채널은 눈 깜빡임 오염이 크므로 workload 해석은 행동 지표와 **함께** 본다.

### 4가지 질문에 대한 계산
| 질문 | 계산 | 코드 |
|---|---|---|
| Q1 어느 문제에서 집중이 가장 오래 유지되나 | 블록별 '휴식보다 engagement 가 높은 창 비율(retention)', 과제별 평균 → 최대 | `block_eeg_summary`, `answer_questions` |
| Q2 어느 과제에서 빠르게 감소하나 | 블록 안 engagement z 의 분당 기울기(선형회귀) → 가장 음수 | 같음 |
| Q3 피로 누적에 따른 변화 | (a) 과제 누적시간 vs fatigue z 회귀 기울기 (b) 사전·사후 EC 휴식의 α, θ 변화율 (c) 전반/후반 정확도 | `fatigue_analysis` |
| Q4 평소 대비 현재 | 개인 이력 z (≥3회) / 집단 참고값 | `BaselineStore.compare` |

### 지속 집중 시간
1. 과제 구간 창만 이어 붙여 '과제 누적시간' 축 생성
2. engagement z 를 20초 이동 중앙값으로 평활
3. 과제 초반 120초의 평균·SD 를 기준으로 다시 z
4. 이 값이 −1 아래로 **30초 이상 연속** 머무는 첫 시점 = 지속 집중 시간
5. 끝까지 안 떨어지면 "≥ 측정 시간"(censored)으로 표시 → 시연용 15분 세션에서는 '최소 X분'으로 해석

## 3. 행동 지표
| 지표 | 식 | 근거 |
|---|---|---|
| d′ | z(Hit) − z(FA), log-linear 보정 (H = (hits+0.5)/(targets+1)) | Hautus, 1995 |
| 정확도, 평균 RT(정답 일치 반응) | – | – |
| (PVT 사용 시) lapse | RT > 500 ms 비율 | Basner & Dinges, 2011 |

## 4. Brain Profile 점수
육각형 6축 정의, 점수식(100 × Φ(z)), 연령대 임시 기준값, 재검사 변화 판단(RCI)은 **docs/BATTERY.md 4–5절**이 기준이다.
- 세타/베타 비(TBR)를 ADHD 지표로 쓰지 않는다(근거 불충분, Arns et al., 2013).
- P300 절대 잠복기를 임상 연구값과 비교하지 않는다(장비 지연).

## 참고문헌
- Barry, R. J., et al. (2007). EEG differences between eyes-closed and eyes-open resting conditions. *Clinical Neurophysiology*, 118(12), 2765–2773.
- Klimesch, W. (1999). EEG alpha and theta oscillations reflect cognitive and memory performance. *Brain Research Reviews*, 29(2–3), 169–195.
- Corcoran, A. W., et al. (2018). Toward a reliable, automated method of individual alpha frequency (IAF) quantification. *Psychophysiology*, 55(7).
- Pope, A. T., Bogart, E. H., & Bartolome, D. S. (1995). Biocybernetic system evaluates indices of operator engagement in automated task. *Biological Psychology*, 40(1–2), 187–195.
- Gevins, A., et al. (1997). High-resolution EEG mapping of cortical activation related to working memory. *Cerebral Cortex*, 7(4), 374–385.
- Jensen, O., & Tesche, C. D. (2002). Frontal theta activity in humans increases with memory load in a working memory task. *European Journal of Neuroscience*, 15(8), 1395–1399.
- Jap, B. T., et al. (2009). Using EEG spectral components to assess algorithms for detecting fatigue. *Expert Systems with Applications*, 36(2), 2352–2359.
- Wascher, E., et al. (2014). Frontal theta activity reflects distinct aspects of mental fatigue. *Biological Psychology*, 96, 57–65.
- Krigolson, O. E., et al. (2017). Choosing MUSE: Validation of a low-cost, portable EEG system for ERP research. *Frontiers in Neuroscience*, 11, 109.
- Bird, J. J., et al. (2018). A study on mental state classification using EEG-based brain-machine interface. *IEEE Int. Conf. Intelligent Systems (IS)*, 795–800.
- Jaeggi, S. M., et al. (2008). Improving fluid intelligence with training on working memory. *PNAS*, 105(19), 6829–6833.
- Owen, A. M., et al. (2005). N-back working memory paradigm: a meta-analysis. *Human Brain Mapping*, 25(1), 46–59.
- Hautus, M. J. (1995). Corrections for extreme proportions and their biasing effects on estimated values of d′. *Behavior Research Methods*, 27, 46–51.
- Coan, J. A., & Allen, J. J. B. (2004). Frontal EEG asymmetry as a moderator and mediator of emotion. *Biological Psychology*, 67, 7–49.
- Donoghue, T., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. *Nature Neuroscience*, 23, 1655–1665.
- Basner, M., & Dinges, D. F. (2011). Maximizing sensitivity of the psychomotor vigilance test (PVT) to sleep loss. *Sleep*, 34(5), 581–591.
- Jacobson, N. S., & Truax, P. (1991). Clinical significance: A statistical approach to defining meaningful change in psychotherapy research. *Journal of Consulting and Clinical Psychology*, 59(1), 12–19.
- Arns, M., et al. (2013). A decade of EEG theta/beta ratio research in ADHD: a meta-analysis. *Journal of Attention Disorders*, 17(5), 374–383.

## 변경 이력
| 날짜 | 변경 | 이유 | 작성 |
|---|---|---|---|
| 2026-10-05 | v1 초기값 | 문헌 기반 출발값 | 담우 |
| 2026-10-07 | 이마 채널 눈 깜빡임 가림 도입, 라이브 품질 판정을 '귀 뒤 기준 + 이마 평균'으로 | 실측에서 눈 뜬 상태의 이마 채널이 깜빡임 때문에 대부분 버려짐(눈 감으면 정상). 가짜 데이터 24회/분 기준 이마 사용 가능 창 0.42 → 0.72 | 담우 |
| 2026-10-08 | 피로 지수를 (θ+α)/β → (θ+α)/(α+β) 로 변경 | (θ+α)/β 는 몰입 지수 β/(α+θ) 의 정확한 역수라 새 정보가 없음 | 담우 |
| 2026-10-06 | 육각형 6축·배터리 도입, 점수식은 BATTERY.md 로 이동 | 인지 과제 조사 반영 | 담우 |
