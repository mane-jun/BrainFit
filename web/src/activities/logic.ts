export type Random = () => number;
export type BinaryScore = {
  target: 0 | 1;
  resp: 0 | 1;
  correct: 0 | 1;
  rt: number;
};

function shuffle<T>(items: T[], random: Random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** 1=흔한 자극, 0=드문 자극. Python brainfit.sequences와 같은 간격 규칙. */
export function rareSequence(
  n: number,
  ratio: number,
  random: Random = Math.random,
): number[] {
  const rareCount = Math.round(n * ratio);
  const rest = n - rareCount * 3;
  if (rest < 0) throw new Error("드문 자극 비율이 너무 높습니다.");
  const units: number[][] = Array.from({ length: rareCount }, () => [1, 1, 0]);
  units.push(...Array.from({ length: rest }, () => [1]));
  return shuffle(units, random).flat();
}

/** 1=드문 타깃, 0=표준. */
export function oddballSequence(
  n: number,
  ratio: number,
  random: Random = Math.random,
): number[] {
  return rareSequence(n, ratio, random).map((x) => 1 - x);
}

export function nbackPositions(
  n: number,
  level: number,
  ratio: number,
  random: Random = Math.random,
) {
  const eligible = shuffle(
    Array.from({ length: n - level }, (_, i) => i + level),
    random,
  );
  const marked = new Set(eligible.slice(0, Math.round((n - level) * ratio)));
  const positions: number[] = [];
  const targets: boolean[] = [];
  for (let i = 0; i < n; i++) {
    const target = marked.has(i);
    const choices = Array.from({ length: 9 }, (_, x) => x).filter(
      (x) => target || i < level || x !== positions[i - level],
    );
    positions.push(
      target
        ? positions[i - level]
        : choices[Math.floor(random() * choices.length)],
    );
    targets.push(target);
  }
  return { positions, targets };
}

export function binaryScore(
  target: 0 | 1,
  reactionSec: number | null,
): BinaryScore {
  const valid = reactionSec !== null && reactionSec >= 0.15;
  const resp: 0 | 1 = valid ? 1 : 0;
  return {
    target,
    resp,
    correct: Number(resp === target) as 0 | 1,
    rt: valid ? reactionSec : -1,
  };
}

export const COLORS = [
  { name: "빨강", hex: "#dc5350" },
  { name: "파랑", hex: "#4e87d9" },
  { name: "초록", hex: "#299768" },
  { name: "노랑", hex: "#d6a83c" },
];

export function stroopQuestion(
  congruent: boolean,
  random: Random = Math.random,
) {
  const inkIndex = Math.floor(random() * COLORS.length);
  const other = COLORS.map((_, i) => i).filter((i) => i !== inkIndex);
  const wordIndex = congruent
    ? inkIndex
    : other[Math.floor(random() * other.length)];
  return {
    word: COLORS[wordIndex].name,
    ink: COLORS[inkIndex].name,
    inkHex: COLORS[inkIndex].hex,
    options: COLORS.map((c) => c.name),
    congruent,
  };
}

export function arithmeticQuestion(
  level: number,
  random: Random = Math.random,
) {
  const low = level === 1 ? 3 : level === 2 ? 10 : 20;
  const high = level === 1 ? 12 : level === 2 ? 29 : 79;
  const pick = () => low + Math.floor(random() * (high - low + 1));
  const a = pick(),
    b = pick(),
    plus = random() < 0.5;
  const answer = plus ? a + b : Math.abs(a - b);
  const expression = plus
    ? `${a} + ${b}`
    : `${Math.max(a, b)} − ${Math.min(a, b)}`;
  const gap = level === 1 ? 2 : level === 2 ? 5 : 10;
  const options = shuffle([answer, answer + gap, answer + gap * 2], random);
  return { expression, answer, options };
}

const WORDS = [
  "바다",
  "연필",
  "토끼",
  "시계",
  "나무",
  "기차",
  "우산",
  "사과",
  "별빛",
  "의자",
  "풍선",
  "강물",
  "거울",
  "책상",
  "고양이",
  "구름",
  "안경",
  "나비",
  "커피",
  "장갑",
  "달력",
  "촛불",
  "지도",
  "도토리",
];

export function wordMemorySet(random: Random = Math.random) {
  const words = shuffle(WORDS, random);
  const study = words.slice(0, 8);
  const probes = shuffle(
    [
      ...study.map((word) => ({ word, target: 1 as const })),
      ...words.slice(8, 16).map((word) => ({ word, target: 0 as const })),
    ],
    random,
  );
  return { study, probes };
}
