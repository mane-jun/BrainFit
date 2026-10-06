# VS Code + GitHub 연결 가이드 (Windows)

대상 저장소: `mane-jun/BrainFit` (Public) · 로컬 작업 폴더: `C:\Users\윤가현\Desktop\대학교\비교과활동\2026\인융대 메이커톤`

---

## 0. 먼저 할 일: 협업 초대 수락
저장소 주인(mane-jun)이 보낸 초대를 수락해야 push 할 수 있다. 메일의 *View invitation* 또는 `https://github.com/mane-jun/BrainFit/invitations` 에서 Accept.

## 1. 설치 (한 번만)
| 프로그램 | 확인 명령 (PowerShell) | 비고 |
|---|---|---|
| Git for Windows (git-scm.com) | `git --version` | 설치 중 기본값 그대로, "Git Credential Manager" 포함 |
| Python 3.11 (python.org) | `py -3.11 --version` | 설치 첫 화면 **Add python.exe to PATH** 체크 |
| VS Code | `code --version` | 확장: Python, Pylance, Ruff, GitHub Pull Requests, (선택) GitLens |

## 2. Git 기본 설정 (한 번만)
```powershell
git config --global user.name  "윤담우"
git config --global user.email "GitHub에 등록된 이메일"
git config --global init.defaultBranch main
git config --global core.autocrlf true      # Windows 줄바꿈 자동 처리
git config --global core.quotepath false    # 한글 파일명 깨짐 방지
```

## 3. GitHub 인증 — 둘 중 하나
### 방법 A. HTTPS (가장 쉬움, 추천)
처음 push 할 때 브라우저 로그인 창이 뜨고(Git Credential Manager) 한 번 로그인하면 끝. 원격 주소는 `https://github.com/mane-jun/BrainFit.git`.

### 방법 B. SSH (스크린샷의 Quick setup 이 SSH 로 되어 있음)
```powershell
ssh-keygen -t ed25519 -C "GitHub 이메일"     # 엔터 3번 (기본 위치 C:\Users\윤가현\.ssh)
# 관리자 PowerShell 에서 한 번:
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
# 일반 PowerShell:
ssh-add $env:USERPROFILE\.ssh\id_ed25519
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard   # 공개키 복사
```
GitHub → 오른쪽 위 프로필 → **Settings → SSH and GPG keys → New SSH key** → 붙여넣기.
확인: `ssh -T git@github.com` → "Hi <아이디>! You've successfully authenticated" 가 나오면 성공.

## 4. 폴더 구성 원칙
```
인융대 메이커톤\                ← 기획안·서약서 등 개인 문서 (Git 에 안 올림)
 └─ BrainFit\                   ← Git 저장소 (코드·문서만)
C:\EEGData\                     ← 실측 뇌파 데이터 (영문 경로, Git 에 안 올림)
```
- 저장소를 상위 폴더 자체로 만들면 서약서(실명) 같은 파일이 실수로 공개 저장소에 올라갈 수 있다 → **하위 폴더 `BrainFit`** 으로 분리.
- Git 은 한글 경로에서도 잘 동작한다. 단 LabRecorder 등 일부 프로그램은 한글 경로에서 실패하므로 데이터는 `C:\EEGData`.

## 5. 저장소 연결 — 상황에 맞는 하나만
현재 원격 저장소는 **비어 있다**. 누가 먼저 올릴지 팀장/저장소 주인과 정한다.

### 5-A. 내가 처음 올리는 경우 (스타터 zip 사용)
```powershell
cd "C:\Users\윤가현\Desktop\대학교\비교과활동\2026\인융대 메이커톤"
# brainfit-starter.zip 을 여기에 풀어서 폴더 이름을 BrainFit 으로
cd BrainFit
git init
git add .
git commit -m "chore: BrainFit 스타터 (분석 파이프라인, 과제 앱, CLAUDE.md, 문서)"
git branch -M main
git remote add origin https://github.com/mane-jun/BrainFit.git   # SSH 면 git@github.com:mane-jun/BrainFit.git
git push -u origin main
```

### 5-B. 이미 누가 올린 경우
```powershell
cd "C:\Users\윤가현\Desktop\대학교\비교과활동\2026\인융대 메이커톤"
git clone https://github.com/mane-jun/BrainFit.git
cd BrainFit
```
스타터 파일을 합쳐야 하면 브랜치를 따서 복사 후 PR (`git switch -c chore/scaffold`).

## 6. VS Code 로 열기 + 파이썬 환경
```powershell
cd "C:\Users\윤가현\Desktop\대학교\비교과활동\2026\인융대 메이커톤\BrainFit"
code .
```
VS Code 터미널(Ctrl+`)에서:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
# "스크립트를 실행할 수 없습니다" 오류 시 한 번만:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
pytest -q                                         # 모두 passed 면 정상
python scripts/analyze_session.py --synthetic     # outputs\ 에 그림 8장
```
`Ctrl+Shift+P → Python: Select Interpreter → .venv` 선택.

## 7. 매일 쓰는 협업 흐름
```powershell
git switch main
git pull                                  # 1) 최신 받기
git switch -c feat/baseline-iaf           # 2) 작업 브랜치
# ... 코드 수정, pytest 통과 확인 ...
git add -A
git commit -m "feat(baseline): IAF 무게중심 계산 추가"
git push -u origin feat/baseline-iaf      # 3) 올리기
```
4) GitHub 에 뜨는 **Compare & pull request** → 템플릿 채우기 → 리뷰어 지정 → CI(초록 체크) 확인 → **Squash and merge**
5) 머지 후: `git switch main; git pull; git branch -d feat/baseline-iaf`

VS Code 화면으로 하려면: 왼쪽 **소스 제어(Ctrl+Shift+G)** 에서 변경 확인·커밋·동기화, 왼쪽 아래 상태표시줄의 브랜치 이름 클릭으로 브랜치 생성/전환.

## 8. 저장소 주인(mane-jun)이 해 두면 좋은 설정
- Settings → Branches → `main` 보호 규칙: *Require a pull request before merging*, *Require status checks (CI)*.
- Settings → Collaborators 에 팀원 전원 추가.

## 9. 자주 나는 오류
| 메시지 | 원인 | 해결 |
|---|---|---|
| `Permission denied (publickey)` | SSH 키 미등록 | 3-B 다시, 또는 HTTPS 로 원격 변경 `git remote set-url origin https://...` |
| `rejected ... (fetch first)` | 원격에 내가 없는 커밋 | `git pull --rebase` 후 다시 push |
| `LF will be replaced by CRLF` | 줄바꿈 경고 | 무시해도 됨(.gitattributes 가 처리) |
| 403 / 권한 없음 | 초대 미수락 | 0번 |
| 큰 파일 push 실패 | .xdf 등 데이터 커밋 | `.gitignore` 확인, 데이터는 팀 드라이브 공유 |

## 10. Claude Code 연결
설치·로그인은 공식 문서(https://docs.claude.com/en/docs/claude-code/overview)를 따른다. 저장소 폴더에서 실행하면 루트의 `CLAUDE.md` 와 `.claude/commands/` 를 자동으로 읽는다. 사용 예는 `docs/PROMPTS.md`.
