import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ActivityChoice, ActivityId, TrialPayload } from "../types";
import { ActivityRunner } from "./ActivityRunner";

function choice(activity: ActivityId): ActivityChoice {
  return {
    activity,
    task: activity === "nback" ? "nback2" : activity,
    level: activity === "nback" ? 2 : null,
    name: activity,
    how: "",
    sec: 90,
    mode: "explore",
    reason: "",
    index: 1,
    total: 4,
  };
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("활동 시행 전송", () => {
  it.each([
    ["gonogo", 40],
    ["nback", 34],
    ["oddball", 72],
    ["pvt", 12],
    ["stroop", 40],
    ["arithmetic", 15],
    ["word_memory", 16],
  ] as const)(
    "%s 활동의 모든 실제 시행을 순서대로 전송한다",
    async (activity, count) => {
      vi.useFakeTimers({
        toFake: [
          "setTimeout",
          "clearTimeout",
          "requestAnimationFrame",
          "cancelAnimationFrame",
          "performance",
        ],
      });
      const trials: TrialPayload[] = [];
      const done = vi.fn(async () => undefined);
      const error = vi.fn();
      render(
        <ActivityRunner
          choice={choice(activity)}
          block={2}
          onTrial={async (trial) => {
            trials.push(trial);
          }}
          onDone={done}
          onError={error}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300_000);
      });
      expect(error).not.toHaveBeenCalled();
      expect(done).toHaveBeenCalledTimes(1);
      expect(trials).toHaveLength(count);
      expect(trials.map((trial) => trial.idx)).toEqual(
        Array.from({ length: count }, (_, i) => i),
      );
      expect(
        trials.every(
          (trial) => trial.task === choice(activity).task && trial.block === 2,
        ),
      ).toBe(true);
      expect(
        trials.every((trial) => trial.target === 0 || trial.target === 1),
      ).toBe(true);
      expect(
        trials.every((trial) => trial.correct === 0 || trial.correct === 1),
      ).toBe(true);
    },
  );

  it("버튼 입력을 실제 반응으로 기록한다", async () => {
    vi.useFakeTimers({
      toFake: [
        "setTimeout",
        "clearTimeout",
        "requestAnimationFrame",
        "cancelAnimationFrame",
        "performance",
      ],
    });
    const trials: TrialPayload[] = [];
    render(
      <ActivityRunner
        choice={choice("gonogo")}
        block={1}
        onTrial={async (trial) => {
          trials.push(trial);
        }}
        onDone={async () => undefined}
        onError={() => undefined}
      />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3400);
    });
    const button = screen.getByRole("button", { name: /반응하기/ });
    fireEvent.click(button);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    expect(trials[0]?.resp).toBe(1);
    expect(trials[0]?.rt).toBeGreaterThanOrEqual(0.15);
  });
});
