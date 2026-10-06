---
description: 커밋 정리 후 PR 본문 초안 작성
---
1. `ruff check .` 와 `pytest -q` 를 실행해 통과를 확인하라 (실패 시 중단하고 보고).
2. `git status` 로 데이터 파일(.xdf, data/sessions, data/users, 개인정보)이 스테이징되지 않았는지 확인하라.
3. 변경 내용을 .github/PULL_REQUEST_TEMPLATE.md 형식으로 채운 PR 본문을 출력하라.
   제목은 Conventional Commits 형식. 관련 docs/plans 문서와 PLAN.md 의 PR 번호를 연결하라.
4. push 명령은 사용자에게 보여주기만 하고 직접 실행하지 마라.
