"""LSL 마커 송신기.

과제 프로그램이 '지금 무슨 일이 일어났는지'를 LSL 마커 스트림으로 보내면,
LabRecorder 가 EEG 와 마커를 **같은 시계**로 한 XDF 파일에 저장한다 → 시점 맞추기 자동 해결.

pylsl 이 없거나 실패하면 CSV 로그만 남긴다(분석은 가능하지만 EEG 와 시점 맞추기는 수동).
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.io import format_marker  # noqa: E402


class MarkerOutlet:
    def __init__(self, name: str = "BrainFitMarkers", log_path: str | Path | None = None):
        self.outlet = None
        self.clock = time.perf_counter
        try:
            from pylsl import StreamInfo, StreamOutlet, local_clock

            info = StreamInfo(name, "Markers", 1, 0, "string", f"{name}-uid")
            self.outlet = StreamOutlet(info)
            self.clock = local_clock
            print(f"[markers] LSL 스트림 '{name}' 송신 시작 — LabRecorder 에서 Update 후 체크하세요.")
        except Exception as e:  # noqa: BLE001
            print(f"[markers] pylsl 사용 불가({e}) → CSV 로그만 기록합니다.")
        self._f = None
        if log_path:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            self._f = open(log_path, "w", newline="", encoding="utf-8")
            self._w = csv.writer(self._f)
            self._w.writerow(["lsl_time", "marker"])

    def push(self, event: str, **attrs) -> str:
        text = format_marker(event, **attrs)
        ts = self.clock()
        if self.outlet is not None:
            self.outlet.push_sample([text], ts)
        if self._f:
            self._w.writerow([f"{ts:.6f}", text])
            self._f.flush()
        return text

    def close(self):
        if self._f:
            self._f.close()
