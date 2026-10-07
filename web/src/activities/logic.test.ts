import { describe, expect, it } from "vitest";
import {
  arithmeticQuestion,
  binaryScore,
  nbackPositions,
  oddballSequence,
  rareSequence,
  stroopQuestion,
  wordMemorySet,
} from "./logic";

function seeded(seed: number) {
  let state = seed;
  return () => (state = (state * 1664525 + 1013904223) >>> 0) / 2 ** 32;
}

describe("자극 순서와 채점", () => {
  it("Go/No-Go의 드문 자극은 정확히 25%이며 앞에 Go가 두 번 나온다", () => {
    const sequence = rareSequence(40, 0.25, seeded(1));
    expect(sequence).toHaveLength(40);
    expect(sequence.filter((x) => x === 0)).toHaveLength(10);
    sequence.forEach((x, i) => {
      if (x === 0) expect(sequence.slice(i - 2, i)).toEqual([1, 1]);
    });
  });

  it("Oddball 타깃은 20%이며 연속 출현하지 않는다", () => {
    const sequence = oddballSequence(80, 0.2, seeded(2));
    expect(sequence.filter((x) => x === 1)).toHaveLength(16);
    sequence.forEach((x, i) => {
      if (x === 1) expect(sequence.slice(i - 2, i)).toEqual([0, 0]);
    });
  });

  it("N-back은 타깃의 실제 위치 관계와 라벨이 일치한다", () => {
    const { positions, targets } = nbackPositions(30, 2, 0.3, seeded(3));
    expect(positions).toHaveLength(30);
    expect(targets.filter(Boolean).length).toBeGreaterThanOrEqual(7);
    targets.forEach((target, i) =>
      expect(target).toBe(i >= 2 && positions[i] === positions[i - 2]),
    );
  });

  it("150ms 미만 반응은 무효이며 미응답과 오반응을 정확히 채점한다", () => {
    expect(binaryScore(1, 0.12)).toEqual({
      target: 1,
      resp: 0,
      correct: 0,
      rt: -1,
    });
    expect(binaryScore(0, 0.35)).toEqual({
      target: 0,
      resp: 1,
      correct: 0,
      rt: 0.35,
    });
    expect(binaryScore(0, null)).toEqual({
      target: 0,
      resp: 0,
      correct: 1,
      rt: -1,
    });
  });

  it("Stroop은 일치·불일치 모두 글자 색을 정답으로 둔다", () => {
    const same = stroopQuestion(true, seeded(4));
    const different = stroopQuestion(false, seeded(4));
    expect(same.word).toBe(same.ink);
    expect(different.word).not.toBe(different.ink);
    expect(same.options).toContain(same.ink);
  });

  it("암산은 정답 하나와 서로 다른 오답 두 개를 만든다", () => {
    const q = arithmeticQuestion(2, seeded(5));
    expect(new Set(q.options).size).toBe(3);
    expect(q.options).toContain(q.answer);
    expect(q.expression).toMatch(/[+−]/);
  });

  it("단어 기억은 학습 단어 8개와 새 단어 8개를 한 번씩 판정한다", () => {
    const set = wordMemorySet(seeded(6));
    expect(set.study).toHaveLength(8);
    expect(set.probes).toHaveLength(16);
    expect(set.probes.filter((p) => p.target === 1)).toHaveLength(8);
    expect(new Set(set.probes.map((p) => p.word)).size).toBe(16);
    set.probes.forEach((p) =>
      expect(set.study.includes(p.word)).toBe(p.target === 1),
    );
  });
});
