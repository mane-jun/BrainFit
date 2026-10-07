import { useEffect, useRef, useState } from "react";
import type { ActivityChoice, TrialPayload } from "../types";
import {
  arithmeticQuestion,
  binaryScore,
  nbackPositions,
  oddballSequence,
  rareSequence,
  stroopQuestion,
  wordMemorySet,
} from "./logic";

type Prompt = {
  kind: "countdown" | "binary" | "choice" | "study" | "wait" | "fixation";
  title: string;
  hint?: string;
  shape?: "go" | "nogo" | "circle" | "triangle" | "signal";
  gridIndex?: number;
  word?: string;
  ink?: string;
  options?: string[];
  hidden?: boolean;
  current?: number;
  total?: number;
};

const pause = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("중단됨", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", stop);
      resolve();
    }, ms);
    const stop = () => {
      window.clearTimeout(timer);
      reject(new DOMException("중단됨", "AbortError"));
    };
    signal.addEventListener("abort", stop, { once: true });
  });

const frame = () =>
  new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

export function ActivityRunner({
  choice,
  block,
  onTrial,
  onDone,
  onError,
}: {
  choice: ActivityChoice;
  block: number;
  onTrial: (trial: TrialPayload) => Promise<void>;
  onDone: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [prompt, setPrompt] = useState<Prompt>({
    kind: "countdown",
    title: "곧 시작합니다",
  });
  const promptRef = useRef(prompt);
  const takeRef = useRef<(value: number) => void>(() => undefined);
  const callbacks = useRef({ onTrial, onDone, onError });
  useEffect(() => {
    callbacks.current = { onTrial, onDone, onError };
  }, [onTrial, onDone, onError]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const current = promptRef.current;
      if (current.kind === "binary" || current.kind === "wait") {
        if (event.code === "Space" || event.code === "Enter") {
          event.preventDefault();
          takeRef.current(1);
        }
      } else if (current.kind === "choice") {
        const digit = /^Digit([1-4])$/.exec(event.code);
        if (digit) {
          event.preventDefault();
          takeRef.current(Number(digit[1]) - 1);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    let index = 0;
    const display = async (next: Prompt) => {
      setPrompt(next);
      promptRef.current = next;
      await frame();
    };
    const emit = async (
      trial: Omit<TrialPayload, "task" | "block" | "idx">,
    ) => {
      if (signal.aborted) return;
      await callbacks.current.onTrial({
        ...trial,
        task: choice.task,
        block,
        idx: index++,
      });
    };
    const capture = async (
      next: Prompt,
      visibleMs: number,
      totalMs: number,
    ) => {
      await display(next);
      const started = performance.now();
      let selected: number | null = null;
      let reaction: number | null = null;
      takeRef.current = (value) => {
        const elapsed = (performance.now() - started) / 1000;
        if (selected !== null || elapsed < 0.15 || signal.aborted) return;
        selected = value;
        reaction = elapsed;
      };
      await pause(visibleMs, signal);
      if (visibleMs < totalMs)
        setPrompt((previous) => ({ ...previous, hidden: true }));
      await pause(Math.max(0, totalMs - visibleMs), signal);
      takeRef.current = () => undefined;
      return { selected, reaction };
    };
    const countdown = async () => {
      for (let n = 3; n > 0; n--) {
        await display({
          kind: "countdown",
          title: String(n),
          hint: "화면을 보고 준비해 주세요",
        });
        await pause(1000, signal);
      }
    };
    const binary = async (
      target: 0 | 1,
      next: Prompt,
      visibleMs: number,
      totalMs: number,
    ) => {
      const answer = await capture(next, visibleMs, totalMs);
      await emit(
        binaryScore(target, answer.selected === null ? null : answer.reaction),
      );
    };

    const run = async () => {
      await countdown();
      if (choice.activity === "gonogo") {
        const seq = rareSequence(40, 0.25);
        for (let i = 0; i < seq.length; i++) {
          const go = seq[i] === 1;
          await binary(
            go ? 1 : 0,
            {
              kind: "binary",
              title: go ? "누르세요" : "참으세요",
              shape: go ? "go" : "nogo",
              hint: "스페이스바 또는 아래 버튼",
              current: i + 1,
              total: seq.length,
            },
            300,
            800,
          );
          await pause(700 + Math.random() * 400, signal);
        }
      } else if (choice.activity === "nback") {
        const level = choice.level || 2;
        const seq = nbackPositions(34, level, 0.3);
        for (let i = 0; i < seq.positions.length; i++) {
          await binary(
            seq.targets[i] ? 1 : 0,
            {
              kind: "binary",
              title: `${level}-back 위치 기억`,
              gridIndex: seq.positions[i],
              hint: `${level}번 전 위치와 같으면 누르세요`,
              current: i + 1,
              total: seq.positions.length,
            },
            500,
            2500,
          );
        }
      } else if (choice.activity === "oddball") {
        const seq = oddballSequence(72, 0.2);
        for (let i = 0; i < seq.length; i++) {
          const target = seq[i] as 0 | 1;
          await binary(
            target,
            {
              kind: "binary",
              title: "삼각형일 때만 누르세요",
              shape: target ? "triangle" : "circle",
              hint: "스페이스바 또는 아래 버튼",
              current: i + 1,
              total: seq.length,
            },
            250,
            800,
          );
          await pause(200 + Math.random() * 300, signal);
        }
      } else if (choice.activity === "pvt") {
        for (let i = 0; i < 12; i++) {
          await display({
            kind: "wait",
            title: "신호를 기다리세요",
            hint: "초록 신호가 켜지면 바로 누르세요",
            current: i + 1,
            total: 12,
          });
          let falseStart = false;
          takeRef.current = () => {
            falseStart = true;
          };
          await pause(2000 + Math.random() * 4000, signal);
          takeRef.current = () => undefined;
          const answer = await capture(
            {
              kind: "binary",
              title: "지금 누르세요",
              shape: "signal",
              hint: "스페이스바 또는 아래 버튼",
              current: i + 1,
              total: 12,
            },
            1500,
            1500,
          );
          const score = binaryScore(
            1,
            answer.selected === null ? null : answer.reaction,
          );
          await emit({
            ...score,
            correct: falseStart ? 0 : score.correct,
            extra: {
              false_start: falseStart,
              lapse: score.rt < 0 || score.rt > 0.5,
            },
          });
        }
      } else if (choice.activity === "stroop") {
        for (let i = 0; i < 40; i++) {
          const q = stroopQuestion(i % 2 === 0);
          const answer = await capture(
            {
              kind: "choice",
              title: "글자 뜻이 아닌 글자 색을 고르세요",
              word: q.word,
              ink: q.inkHex,
              options: q.options,
              hint: "숫자 1–4 또는 버튼",
              current: i + 1,
              total: 40,
            },
            2000,
            2000,
          );
          await emit({
            target: 1,
            resp: answer.selected === null ? 0 : 1,
            correct: Number(
              answer.selected !== null && q.options[answer.selected] === q.ink,
            ),
            rt: answer.reaction ?? -1,
            extra: { congruent: q.congruent, selected: answer.selected ?? -1 },
          });
        }
      } else if (choice.activity === "arithmetic") {
        let level = 1,
          streak = 0;
        for (let i = 0; i < 15; i++) {
          const trialLevel = level;
          const q = arithmeticQuestion(trialLevel);
          const answer = await capture(
            {
              kind: "choice",
              title: "계산 결과를 고르세요",
              word: q.expression,
              options: q.options.map(String),
              hint: "숫자 1–3 또는 버튼",
              current: i + 1,
              total: 15,
            },
            6000,
            6000,
          );
          const correct = Number(
            answer.selected !== null && q.options[answer.selected] === q.answer,
          );
          streak = correct ? streak + 1 : 0;
          if (streak >= 3) {
            level = Math.min(3, level + 1);
            streak = 0;
          }
          await emit({
            target: 1,
            resp: answer.selected === null ? 0 : 1,
            correct,
            rt: answer.reaction ?? -1,
            extra: { level: trialLevel, selected: answer.selected ?? -1 },
          });
        }
      } else if (choice.activity === "word_memory") {
        const set = wordMemorySet();
        for (let i = 0; i < set.study.length; i++) {
          await display({
            kind: "study",
            title: "단어를 기억해 주세요",
            word: set.study[i],
            hint: `학습 ${i + 1} / 8`,
            current: i + 1,
            total: 24,
          });
          await pause(1500, signal);
        }
        for (let i = 0; i < set.probes.length; i++) {
          const probe = set.probes[i];
          const answer = await capture(
            {
              kind: "choice",
              title: "앞에서 본 단어인가요?",
              word: probe.word,
              options: ["봤어요", "처음 봐요"],
              hint: "1 = 봤어요, 2 = 처음 봐요",
              current: i + 9,
              total: 24,
            },
            3000,
            3000,
          );
          const resp = answer.selected === 0 ? 1 : 0;
          await emit({
            target: probe.target,
            resp,
            correct: Number(answer.selected !== null && resp === probe.target),
            rt: answer.reaction ?? -1,
            extra: { omitted: answer.selected === null },
          });
        }
      }
      await display({ kind: "fixation", title: "활동을 정리하고 있어요" });
      await callbacks.current.onDone();
    };
    run().catch((error: unknown) => {
      if (!signal.aborted)
        callbacks.current.onError(
          error instanceof Error
            ? error.message
            : "활동을 진행하지 못했습니다.",
        );
    });
    return () => {
      controller.abort();
      takeRef.current = () => undefined;
    };
  }, [choice.activity, choice.level, choice.task, block]);

  const choose = (value: number) => takeRef.current(value);
  return (
    <div className="activity-runner" aria-live="polite">
      {prompt.current && (
        <div className="trial-progress">
          시행 {prompt.current} / {prompt.total}
        </div>
      )}
      <h2>{prompt.title}</h2>
      <div className="stimulus-area">
        {prompt.hidden ? (
          <span className="fixation">+</span>
        ) : prompt.gridIndex !== undefined ? (
          <div className="nback-grid">
            {Array.from({ length: 9 }, (_, i) => (
              <div key={i} className={i === prompt.gridIndex ? "lit" : ""} />
            ))}
          </div>
        ) : prompt.shape ? (
          <div className={`stimulus-shape ${prompt.shape}`} />
        ) : prompt.word ? (
          <strong className="stimulus-word" style={{ color: prompt.ink }}>
            {prompt.word}
          </strong>
        ) : (
          <span className="fixation">
            {prompt.kind === "countdown" ? prompt.title : "+"}
          </span>
        )}
      </div>
      <p className="activity-hint">{prompt.hint}</p>
      {(prompt.kind === "binary" || prompt.kind === "wait") && (
        <button className="response-button" onClick={() => choose(1)}>
          반응하기 <kbd>Space</kbd>
        </button>
      )}
      {prompt.kind === "choice" && (
        <div className="choice-grid">
          {prompt.options?.map((option, i) => (
            <button key={`${option}-${i}`} onClick={() => choose(i)}>
              <kbd>{i + 1}</kbd>
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
