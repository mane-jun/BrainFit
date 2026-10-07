import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Results } from "./Results";
import type { LiveResult } from "./types";

afterEach(cleanup);

it("최종 결과에서 실제 수행 기록과 판단 보류를 구분해 보여준다", () => {
  const result: LiveResult = {
    session_id: "test-session",
    brain_type: {
      id: "balanced",
      name: "균형형",
      summary: "기준선에 가까운 상태예요.",
      tip: "",
    },
    activities: [
      {
        activity: "gonogo",
        task: "gonogo",
        block: 1,
        name: "Go / No-Go",
        responsive: true,
        z: { engagement: 0.8, workload: 0.2, fatigue: -0.1 },
        behavior: { n_trials: 40, accuracy: 0.9 },
        feedback: ["반응을 잘 조절했어요."],
      },
      {
        activity: "pvt",
        task: "pvt",
        block: 2,
        name: "빠른 반응",
        responsive: null,
        z: null,
        behavior: { n_trials: 12, accuracy: 0.5 },
        feedback: [],
      },
    ],
    overall: { message: "두 활동을 마쳤습니다." },
  };
  const restart = vi.fn();
  render(<Results result={result} onRestart={restart} />);
  expect(screen.getByText("두 활동을 마쳤습니다.")).toBeTruthy();
  expect(screen.getByText("90%")).toBeTruthy();
  expect(screen.getByText("판단 보류")).toBeTruthy();
  expect(screen.getByText("반응을 잘 조절했어요.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "새 측정 시작" }));
  expect(restart).toHaveBeenCalledTimes(1);
});
