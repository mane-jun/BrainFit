---
description: 승인된 계획서대로 구현하고 테스트까지 통과시킨다
---
계획서: $ARGUMENTS

1. 계획서와 CLAUDE.md 의 'EEG 도메인 규칙'을 다시 읽어라.
2. 현재 브랜치가 main 이면 계획서 주제로 `feat/…` 브랜치를 만들어라.
3. 계획서 범위 안에서만 구현하라. 범위 밖 개선점은 계획서 하단 'TODO' 에 적기만 하라.
4. 새 분석 기능마다 tests/ 에 가짜 데이터(brainfit.synth) 기반 테스트를 추가하라.
5. `ruff check . --fix` 와 `pytest -q` 를 통과시켜라. 실패하면 원인 설명 후 수정.
6. `python scripts/analyze_session.py --synthetic` 이 끝까지 도는지 확인하라.
7. 변경 요약, 테스트 결과, 남은 위험을 보고하라. 커밋은 Conventional Commits 형식으로.
