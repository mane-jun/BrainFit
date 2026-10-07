import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const api = vi.hoisted(() => ({
  start: vi.fn(),
  phase: vi.fn(),
  mark: vi.fn(),
  trial: vi.fn(),
  next: vi.fn(),
  finish: vi.fn(),
}));

vi.mock("./api", () => ({ liveApi: api }));
vi.mock("./LivePanels", () => ({ LivePanels: () => null }));
vi.mock("./useLiveSocket", () => ({
  useLiveSocket: () => ({
    snapshot: null,
    connected: false,
    wave: { TP9: [], AF7: [], AF8: [], TP10: [] },
    trend: [],
    qualityReady: false,
    clear: vi.fn(),
  }),
}));

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  api.start.mockResolvedValue({ session_id: "test" });
  api.phase.mockResolvedValue({ phase: "signal_check" });
  api.mark.mockImplementation(async (event: string) =>
    event === "rest_ec_end"
      ? { brain_type: { name: "테스트", summary: "", tip: "" } }
      : {},
  );
  api.trial.mockResolvedValue({ ok: true });
  api.next
    .mockResolvedValueOnce({
      activity: "gonogo",
      task: "gonogo",
      level: null,
      name: "Go/No-Go",
      how: "",
      sec: 90,
      mode: "explore",
      reason: "",
      index: 1,
      total: 1,
    })
    .mockResolvedValue({ activity: null, reason: "완료" });
  api.finish.mockResolvedValue({
    session_id: "test",
    brain_type: null,
    activities: [],
    overall: { message: "판단할 수 있는 활동 데이터가 부족해요." },
  });
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

async function reachActivityIntro() {
  render(<App />);
  fireEvent.change(screen.getByLabelText("측정 모드"), {
    target: { value: "test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "뇌파 테스트 시작" }));
  await screen.findByRole("button", { name: "착용 확인 건너뛰기" });
  fireEvent.click(screen.getByRole("button", { name: "착용 확인 건너뛰기" }));
  await screen.findByRole("button", { name: "눈 뜬 휴식 건너뛰기" });
  fireEvent.click(screen.getByRole("button", { name: "눈 뜬 휴식 건너뛰기" }));
  await screen.findByRole("button", { name: "눈 감은 휴식 건너뛰기" });
  fireEvent.click(
    screen.getByRole("button", { name: "눈 감은 휴식 건너뛰기" }),
  );
  await screen.findByRole("button", { name: "첫 활동 보기" });
  fireEvent.click(screen.getByRole("button", { name: "첫 활동 보기" }));
  await screen.findByRole("button", { name: "활동 건너뛰기" });
}

describe("테스트 측정 모드", () => {
  it("착용·휴식·활동을 건너뛰어도 마커 순서를 지키며 결과까지 이동한다", async () => {
    await reachActivityIntro();
    fireEvent.click(screen.getByRole("button", { name: "활동 건너뛰기" }));
    await waitFor(() => expect(api.finish).toHaveBeenCalledTimes(1));
    expect(api.mark.mock.calls.map(([event]) => event)).toEqual([
      "rest_eo_start",
      "rest_eo_end",
      "rest_ec_start",
      "rest_ec_end",
      "block_start",
      "block_end",
    ]);
    expect(api.trial).not.toHaveBeenCalled();
  });

  it("시작한 활동도 건너뛰면 다음 단계로 이동한다", async () => {
    await reachActivityIntro();
    fireEvent.click(screen.getByRole("button", { name: "활동 시작" }));
    await screen.findByRole("button", { name: "진행 중인 활동 건너뛰기" });
    fireEvent.click(
      screen.getByRole("button", { name: "진행 중인 활동 건너뛰기" }),
    );
    await waitFor(() => expect(api.finish).toHaveBeenCalledTimes(1));
    expect(api.mark.mock.calls.map(([event]) => event).slice(-2)).toEqual([
      "block_start",
      "block_end",
    ]);
  });
});

describe("화면 테마", () => {
  it("라이트·다크 선택을 즉시 적용하고 새로고침 후에도 유지한다", () => {
    render(<App />);
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "다크" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("brainfit-theme")).toBe("dark");
    expect(
      screen.getByRole("button", { name: "다크" }).getAttribute("aria-pressed"),
    ).toBe("true");

    cleanup();
    render(<App />);
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "라이트" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("brainfit-theme")).toBe("light");
  });
});
