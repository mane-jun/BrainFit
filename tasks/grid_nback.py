"""측정 세션 실행기: 기준선 휴식(EO/EC) → Grid N-back 블록 → 사후 눈감기 휴식.

Grid N-back (시공간 작업기억 과제, Jaeggi et al., 2008 의 위치 과제와 같은 구조)
  - 3×3 격자 중 한 칸이 0.5초 켜지고, 2.5초 쉬고 다음 칸 (시행 1개 = 3초)
  - 지금 위치가 N번 전 위치와 같으면 SPACE
  - N=0(대조: 가운데 칸이면 SPACE) / 1 / 2 / 3(어려움)
    → 난이도에 따라 전두 세타↑·알파↓ 가 나타나는지 본다 (0-back 은 '기억 부담 0' 기준 조건)

실행 순서 (중요!)
  1) BlueMuse 스트리밍 시작
  2) python tasks/grid_nback.py --user damwoo   ← 이 창이 '대기 화면'에서 멈춰 있음
  3) LabRecorder 에서 Update → Muse EEG 와 BrainFitMarkers 둘 다 체크 → Start
  4) 과제 창으로 돌아와 SPACE → 측정 시작
  5) 끝나면 LabRecorder Stop

키: SPACE = 일치 / ESC = 중단
테스트용: python tasks/grid_nback.py --auto --speed 20   (화면 없이 자동 응답, 20배속)
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markers import MarkerOutlet  # noqa: E402

STIM_SEC, TRIAL_SEC = 0.5, 3.0
BG, FG, GRID, LIT = (18, 18, 24), (230, 230, 235), (70, 70, 85), (80, 150, 255)


ZERO_BACK_TARGET = 4  # 0-back: '가운데 칸'이 켜지면 SPACE (기억 부담 없는 주의 대조 조건)


def is_target(seq: list[int], i: int, n: int) -> int:
    if n == 0:
        return int(seq[i] == ZERO_BACK_TARGET)
    return int(i >= n and seq[i] == seq[i - n])


def make_sequence(n: int, n_trials: int, p_target: float = 0.3, rng=random) -> list[int]:
    seq = [rng.randrange(9) for _ in range(n_trials)]
    if n == 0:
        return [ZERO_BACK_TARGET if rng.random() < p_target
                else rng.choice([p for p in range(9) if p != ZERO_BACK_TARGET]) for _ in seq]
    for i in range(n, n_trials):
        if rng.random() < p_target:
            seq[i] = seq[i - n]
        elif seq[i] == seq[i - n]:  # 우연한 일치 방지
            seq[i] = (seq[i] + rng.randrange(1, 9)) % 9
    return seq


class App:
    def __init__(self, a):
        self.a = a
        if a.auto:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame

        self.pg = pygame
        pygame.init()
        flags = pygame.FULLSCREEN if a.fullscreen else 0
        self.screen = pygame.display.set_mode((0, 0) if a.fullscreen else (900, 900), flags)
        pygame.display.set_caption("BrainFit — Grid N-back")
        self.font = self._font(40)
        self.small = self._font(26)
        self.clock = pygame.time.Clock()
        self.beep = self._make_beep()
        sid = f"{datetime.now():%Y%m%d_%H%M%S}_{a.user}"
        self.dir = Path(a.out) / sid
        self.mk = MarkerOutlet(log_path=self.dir / "markers.csv")
        self.beh = open(self.dir / "behavior.csv", "w", newline="", encoding="utf-8")
        self.bw = csv.writer(self.beh)
        self.bw.writerow(["task", "block", "idx", "pos", "target", "resp", "correct", "rt"])
        self.rng = random.Random(a.seed)
        self.nb_stim, self.nb_trial = STIM_SEC, TRIAL_SEC  # 모드별로 바꿀 수 있게

    # ── 유틸 ────────────────────────────────────────────────────────
    def _font(self, size):
        for name in ("malgungothic", "applegothic", "nanumgothic", "notosanscjkkr"):
            path = self.pg.font.match_font(name)
            if path:
                return self.pg.font.Font(path, size)
        return self.pg.font.Font(None, size)

    def _make_beep(self):
        try:
            import numpy as np

            self.pg.mixer.init(frequency=44100, size=-16, channels=1)
            t = np.arange(int(44100 * 0.3)) / 44100
            wave = (np.sin(2 * np.pi * 880 * t) * 12000).astype(np.int16)
            return self.pg.sndarray.make_sound(wave)
        except Exception:  # noqa: BLE001
            return None

    def wait(self, sec: float):
        """sec 동안 대기하며 키 입력을 모은다. [(키, 경과초)] 반환"""
        sec = sec / self.a.speed
        start = self.pg.time.get_ticks()
        keys = []
        while (el := (self.pg.time.get_ticks() - start) / 1000) < sec:
            for e in self.pg.event.get():
                if e.type == self.pg.QUIT or (e.type == self.pg.KEYDOWN and e.key == self.pg.K_ESCAPE):
                    self.abort()
                if e.type == self.pg.KEYDOWN:
                    keys.append((e.key, el * self.a.speed))
            self.clock.tick(240)
        return keys

    def text(self, lines, y0=None):
        self.screen.fill(BG)
        h = self.screen.get_height()
        y = y0 or h // 2 - len(lines) * 30
        for ln in lines:
            s = self.font.render(ln, True, FG) if ln else None
            if s:
                self.screen.blit(s, s.get_rect(center=(self.screen.get_width() // 2, y)))
            y += 60
        self.pg.display.flip()

    def fixation(self):
        self.screen.fill(BG)
        cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
        self.pg.draw.line(self.screen, FG, (cx - 25, cy), (cx + 25, cy), 4)
        self.pg.draw.line(self.screen, FG, (cx, cy - 25), (cx, cy + 25), 4)
        self.pg.display.flip()

    def grid(self, lit: int | None):
        self.screen.fill(BG)
        w, h = self.screen.get_size()
        cell = min(w, h) // 5
        ox, oy = (w - 3 * cell) // 2, (h - 3 * cell) // 2
        for i in range(9):
            r = self.pg.Rect(ox + (i % 3) * cell + 6, oy + (i // 3) * cell + 6, cell - 12, cell - 12)
            self.pg.draw.rect(self.screen, LIT if i == lit else GRID, r, 0 if i == lit else 3,
                              border_radius=12)
        self.pg.display.flip()

    def wait_space(self):
        if self.a.auto:
            return
        while True:
            for e in self.pg.event.get():
                if e.type == self.pg.KEYDOWN and e.key == self.pg.K_SPACE:
                    return
                if e.type == self.pg.QUIT or (e.type == self.pg.KEYDOWN and e.key == self.pg.K_ESCAPE):
                    self.abort()
            self.clock.tick(60)

    def abort(self):
        self.mk.push("session_abort")
        self.close()
        sys.exit(0)

    def close(self):
        self.mk.close()
        self.beh.close()
        self.pg.quit()
        print(f"[session] 저장 폴더: {self.dir}")

    # ── 단계 ────────────────────────────────────────────────────────
    def rest(self, name: str, eyes_closed: bool):
        if eyes_closed:
            self.text(["눈을 감고 편하게 쉬세요.", "삐- 소리가 나면 눈을 뜨세요.", "", "(SPACE 로 시작)"])
        else:
            self.text(["화면 가운데 + 를 편하게 바라보세요.", "몸과 턱에 힘을 빼고 움직이지 마세요.", "",
                       "(SPACE 로 시작)"])
        self.wait_space()
        self.fixation() if not eyes_closed else self.text(["눈을 감아 주세요"])
        self.wait(1.0)
        self.mk.push(f"{name}_start")
        self.wait(self.a.rest_sec)
        self.mk.push(f"{name}_end")
        if self.beep:
            self.beep.play()

    def block(self, n: int, block_id: int):
        task = f"nback{n}"
        n_trials = self.a.trials + n
        seq = make_sequence(n, n_trials, rng=self.rng)
        rule = ("가운데 칸이 켜지면 SPACE" if n == 0 else f"지금 위치가 {n}번 전 위치와 같으면 SPACE")
        self.text([f"{n}-back", rule, "", "(SPACE 로 시작)"])
        self.wait_space()
        self.fixation()
        self.wait(2.0)
        self.mk.push("block_start", task=task, block=block_id, n=n)
        for i, pos in enumerate(seq):
            target = is_target(seq, i, n)
            self.grid(pos)
            self.mk.push("stim", task=task, block=block_id, idx=i, pos=pos, target=target)
            keys = self.wait(self.nb_stim)
            self.grid(None)
            keys += [(k, t + self.nb_stim) for k, t in self.wait(self.nb_trial - self.nb_stim)]
            presses = [t for k, t in keys if k == self.pg.K_SPACE]
            if self.a.auto:  # 자동 모드: 난이도 높을수록 실수가 많은 가상 응답
                hit = self.rng.random() < (0.97 - 0.12 * max(n - 1, 0))
                fa = self.rng.random() < (0.02 + 0.05 * max(n - 1, 0))
                presses = [round(self.rng.uniform(0.4, 1.0), 3)] if (hit if target else fa) else []
            resp = int(bool(presses))
            rt = round(presses[0], 3) if presses else -1
            if resp:
                self.mk.push("response", task=task, block=block_id, idx=i, rt=rt)
            correct = int(resp == target)
            self.mk.push("trial", task=task, block=block_id, idx=i, pos=pos, target=target,
                         resp=resp, correct=correct, rt=rt)
            self.bw.writerow([task, block_id, i, pos, target, resp, correct, rt])
        self.mk.push("block_end", task=task, block=block_id, n=n)

    def run(self):
        self.text(["BrainFit 측정", "", "LabRecorder 에서 EEG + BrainFitMarkers 를",
                   "체크하고 Start 를 누른 뒤", "SPACE 를 누르세요."])
        self.wait_space()
        self.mk.push("session_start", user=self.a.user, protocol="v1")
        self.rest("rest_eo", eyes_closed=False)
        self.rest("rest_ec", eyes_closed=True)
        levels = [int(x) for x in self.a.levels.split(",")]
        for b, n in enumerate(levels, start=1):
            self.block(n, b)
            if b < len(levels):
                self.text(["잠깐 쉬세요"])
                self.wait(self.a.between)
        if not self.a.no_post:
            self.rest("rest_ec_post", eyes_closed=True)
        self.mk.push("session_end")
        self.text(["수고하셨습니다!", "LabRecorder 에서 Stop 을 누르세요."])
        self.wait(2.0)
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="anon")
    ap.add_argument("--levels", default="1,2,3,2,3,1", help="블록 순서 (N 값)")
    ap.add_argument("--trials", type=int, default=20, help="블록당 기본 시행 수 (+N)")
    ap.add_argument("--rest-sec", type=float, default=60)
    ap.add_argument("--between", type=float, default=15)
    ap.add_argument("--no-post", action="store_true", help="사후 눈감기 휴식 생략")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--out", default="data/sessions")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--auto", action="store_true", help="테스트용 자동 응답(화면 없음)")
    ap.add_argument("--speed", type=float, default=1.0, help="테스트용 배속")
    App(ap.parse_args()).run()


if __name__ == "__main__":
    main()
