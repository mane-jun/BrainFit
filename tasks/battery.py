"""BrainFit Cognitive Battery — 한 번 앉아서 1번(기준선)·2번(과제)·3번(상태) 데이터를 모두 얻는 세션.

순서 (docs/BATTERY.md)
  기준선 EO → EC → [PVT(노년층)] → Go/No-Go → Grid N-back → Visual Oddball → 사후 EC

  python tasks/battery.py --user p01 --mode standard     # 성인 약 15분
  python tasks/battery.py --user s01 --mode senior       # 노년층 약 15분
  python tasks/battery.py --user demo --mode demo        # 시연 약 6분
  python tasks/battery.py --auto --speed 40 --mode demo  # 화면 없이 테스트

키: SPACE = 반응 / ESC = 중단
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grid_nback import App  # noqa: E402

from brainfit.config import BATTERY_MODES  # noqa: E402
from brainfit.sequences import gonogo_sequence, oddball_sequence  # noqa: E402

GO_COL, NOGO_COL, STD_COL, TGT_COL = (70, 200, 120), (230, 80, 80), (200, 200, 210), (255, 200, 60)
ANTICIPATION = 0.15  # 150 ms 미만 반응은 '예측 반응'으로 무효 처리


class Battery(App):
    def __init__(self, a):
        super().__init__(a)
        self.m = BATTERY_MODES[a.mode]
        self.scale = 1.4 if a.mode == "senior" else 1.0  # 노년층: 자극 크게

    # ── 그리기 ──────────────────────────────────────────────────────
    def shape(self, kind: str):
        """Go=초록 원, No-Go=빨간 사각형(색각 이상 대비 모양도 다르게), 표준=회색 원, 타깃=노란 삼각형"""
        pg = self.pg
        self.screen.fill((18, 18, 24))
        cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
        r = int(90 * self.scale)
        if kind == "go":
            pg.draw.circle(self.screen, GO_COL, (cx, cy), r)
        elif kind == "nogo":
            pg.draw.rect(self.screen, NOGO_COL, pg.Rect(cx - r, cy - r, 2 * r, 2 * r))
        elif kind == "std":
            pg.draw.circle(self.screen, STD_COL, (cx, cy), r, width=10)
        elif kind == "tgt":
            pg.draw.polygon(self.screen, TGT_COL, [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)])
        pg.display.flip()

    def _presses(self, keys):
        return [t for k, t in keys if k == self.pg.K_SPACE and t >= ANTICIPATION]

    def _auto(self, target: int, p_hit: float, p_fa: float, rt_mu: float):
        go = self.rng.random() < (p_hit if target else p_fa)
        return [max(0.16, self.rng.gauss(rt_mu, 0.07))] if go else []

    def intro(self, lines):
        self.text(lines + ["", "(SPACE 로 시작)"])
        self.wait_space()
        self.fixation()
        self.wait(2.0)

    # ── 과제 ────────────────────────────────────────────────────────
    def gonogo(self, block_id: int):
        c, task = self.m["gonogo"], "gonogo"
        self.intro(["Go / No-Go", "초록 원 → 최대한 빨리 SPACE", "빨간 사각형 → 누르지 마세요"])
        seq = gonogo_sequence(c["n"], c["p_nogo"], self.rng)
        self.mk.push("block_start", task=task, block=block_id)
        for i, go in enumerate(seq):
            self.shape("go" if go else "nogo")
            self.mk.push("stim", task=task, block=block_id, idx=i, target=go)
            keys = self.wait(c["stim"])
            self.fixation()
            keys += [(k, t + c["stim"]) for k, t in self.wait(c["window"] - c["stim"])]
            presses = self._presses(keys)
            if self.a.auto:
                presses = self._auto(go, 0.97, 0.18, 0.38)
            self._log_trial(task, block_id, i, -1, go, presses)
            self.wait(self.rng.uniform(*c["iti"]))
        self.mk.push("block_end", task=task, block=block_id)

    def oddball(self, block_id: int):
        c, task = self.m["oddball"], "oddball"
        self.intro(["Oddball", "대부분 동그라미가 나옵니다.", "노란 삼각형이 나올 때만 SPACE"])
        seq = oddball_sequence(c["n"], c["p_target"], self.rng)
        self.mk.push("block_start", task=task, block=block_id)
        for i, tgt in enumerate(seq):
            self.shape("tgt" if tgt else "std")
            self.mk.push("stim", task=task, block=block_id, idx=i, target=tgt)
            keys = self.wait(c["stim"])
            self.fixation()
            iti = self.rng.uniform(*c["iti"])
            keys += [(k, t + c["stim"]) for k, t in self.wait(iti)]
            presses = self._presses(keys)
            if self.a.auto:
                presses = self._auto(tgt, 0.95, 0.02, 0.45)
            self._log_trial(task, block_id, i, -1, tgt, presses)
        self.mk.push("block_end", task=task, block=block_id)

    def pvt(self, block_id: int):
        c, task = self.m["pvt"], "pvt"
        self.intro(["반응 속도", "가운데에 초록 원이 나타나면", "최대한 빨리 SPACE"])
        self.mk.push("block_start", task=task, block=block_id)
        elapsed, i = 0.0, 0
        while elapsed < c["sec"]:
            isi = self.rng.uniform(*c["isi"])
            early = self._presses(self.wait(isi))       # 자극 전에 누름 = false start
            self.shape("go")
            self.mk.push("stim", task=task, block=block_id, idx=i, target=1)
            keys = []
            start = self.pg.time.get_ticks()
            while (self.pg.time.get_ticks() - start) / 1000 * self.a.speed < c["timeout"]:
                keys += self.wait(0.02)
                if self._presses(keys):
                    break
            presses = self._presses(keys)
            if self.a.auto:
                presses = self._auto(1, 0.95, 0, 0.32)
            self._log_trial(task, block_id, i, -1, 1, presses, extra={"false_start": int(bool(early))})
            self.fixation()
            elapsed += isi + c["timeout"] / 2
            i += 1
        self.mk.push("block_end", task=task, block=block_id)

    def _log_trial(self, task, block_id, i, pos, target, presses, extra=None):
        resp = int(bool(presses))
        rt = round(presses[0], 3) if presses else -1
        if resp:
            self.mk.push("response", task=task, block=block_id, idx=i, rt=rt)
        correct = int(resp == target)
        self.mk.push("trial", task=task, block=block_id, idx=i, target=target, resp=resp,
                     correct=correct, rt=rt, **(extra or {}))
        self.bw.writerow([task, block_id, i, pos, target, resp, correct, rt])

    def break_(self):
        self.text(["잠깐 쉬세요"])
        self.wait(self.m["between"])

    # ── 전체 흐름 ───────────────────────────────────────────────────
    def run(self):
        m = self.m
        self.a.rest_sec = m["rest_sec"]
        nb = m["nback"]
        self.a.trials = nb["trials"]
        self.nb_stim, self.nb_trial = nb["stim"], nb["trial"]

        self.text(["BrainFit 인지 측정", f"모드: {self.a.mode}", "",
                   "LabRecorder 에서 EEG + BrainFitMarkers 체크 → Start", "그다음 SPACE"])
        self.wait_space()
        self.mk.push("session_start", user=self.a.user, protocol=f"battery-{self.a.mode}-v1")
        self.rest("rest_eo", eyes_closed=False)
        self.rest("rest_ec", eyes_closed=True)
        b = 1
        if m["pvt"]:
            self.pvt(b)
            b += 1
            self.break_()
        self.gonogo(b)
        b += 1
        self.break_()
        for n in nb["levels"]:
            self.block(n, b)
            b += 1
            self.break_()
        self.oddball(b)
        if m["post_rest"]:
            self.rest("rest_ec_post", eyes_closed=True)
        self.mk.push("session_end")
        self.text(["수고하셨습니다!", "LabRecorder 에서 Stop 을 누르세요."])
        self.wait(2.0)
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="anon")
    ap.add_argument("--mode", choices=list(BATTERY_MODES), default="standard")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--out", default="data/sessions")
    ap.add_argument("--seed", type=int, default=None, help="재검사 때는 다른 seed(=다른 자극 순서)")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    # App(grid_nback) 가 기대하는 속성 기본값
    a.levels, a.trials, a.rest_sec, a.between, a.no_post = "", 20, 60, 15, False
    Battery(a).run()


if __name__ == "__main__":
    main()
