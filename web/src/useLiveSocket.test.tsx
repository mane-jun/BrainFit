import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useLiveSocket } from "./useLiveSocket";

class MockSocket {
  static latest: MockSocket;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    MockSocket.latest = this;
  }

  close() {
    this.onclose?.();
  }
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("연결이 끊기면 착용 확인을 취소하고 안정 시간을 다시 잰다", () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  let now = 0;
  vi.spyOn(performance, "now").mockImplementation(() => now);
  vi.stubGlobal("WebSocket", MockSocket);
  const { result } = renderHook(() => useLiveSocket());
  const first = MockSocket.latest;
  const tick = {
    type: "tick",
    snapshot: { quality: { TP9: 1, AF7: 1, AF8: 1, TP10: 1 } },
    wave: {
      sfreq: 256,
      ch: ["TP9", "AF7", "AF8", "TP10"],
      data: [[], [], [], []],
    },
  };
  const send = (socket: MockSocket) =>
    socket.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(tick) }),
    );

  act(() => {
    first.onopen?.();
    send(first);
    now = 3100;
    send(first);
  });
  expect(result.current.qualityReady).toBe(true);

  act(() => first.onclose?.());
  expect(result.current.qualityReady).toBe(false);

  act(() => {
    vi.advanceTimersByTime(1000);
    send(MockSocket.latest);
  });
  expect(result.current.qualityReady).toBe(false);
  act(() => {
    now = 6200;
    send(MockSocket.latest);
  });
  expect(result.current.qualityReady).toBe(true);
});
