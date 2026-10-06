---
description: 실측 XDF 를 분석하고 결과를 과장 없이 해석한다
---
인자: $ARGUMENTS   (예: C:/EEGData/exp001/block_Default.xdf p01 senior)

1. `python scripts/analyze_session.py --xdf <경로> --user <ID> --age-band <adult|senior>` 실행.
   마커가 없다는 경고가 나오면 사용자에게 구간 시간을 물어 `--segments` 로 다시 실행.
2. 결과 폴더의 summary.json 과 그림을 읽고 아래 순서로 보고하라.
   ① 품질: 채널별 사용 가능 비율, 끊김(n_gaps). 60% 미만이면 결과보다 재측정 권고를 먼저.
   ② 1번 기준선: 알파 반응성(EC/EO), IAF, 알파 피크가 뚜렷한지.
   ③ 3번 상태: 과제별 engagement/workload z, 지속 집중, 피로 추세, 사전·사후 EC 변화.
   ④ 행동: 과제별 정확도·d′·RT, Go/No-Go 오반응률, Oddball 적중률.
   ⑤ P300: valid 여부, 깨끗한 타깃 에포크 수, 진폭. invalid 면 이유.
   ⑥ 육각형 점수와 추천 — '임시 기준' 임을 명시.
3. 진단적 표현 금지. 확실하지 않은 해석은 '가능성'으로 표현하고 근거가 되는 그림 파일명을 붙여라.
