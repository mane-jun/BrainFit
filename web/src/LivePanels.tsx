import { useEffect, useRef, useState } from "react";
import type { Channel, Snapshot } from "./types";
import { CHANNELS } from "./types";

const NAMES: Record<Channel, string> = {
  TP9: "왼쪽 귀 뒤",
  AF7: "왼쪽 이마",
  AF8: "오른쪽 이마",
  TP10: "오른쪽 귀 뒤",
};
const COLORS: Record<Channel, string> = {
  TP9: "#5ab6dd",
  AF7: "#f0b567",
  AF8: "#ea83aa",
  TP10: "#76c9ac",
};
const POS: Record<Channel, [number, number]> = {
  TP9: [38, 122],
  AF7: [78, 49],
  AF8: [142, 49],
  TP10: [182, 122],
};

function prepare(canvas: HTMLCanvasElement, height: number) {
  const width = canvas.clientWidth || 400;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(ratio, ratio);
  return { ctx, width };
}

function Waveform({ wave }: { wave: Record<Channel, number[]> }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const { ctx, width } = prepare(canvas, 196);
    ctx.clearRect(0, 0, width, 196);
    CHANNELS.forEach((ch, index) => {
      const y0 = index * 49 + 24.5;
      ctx.strokeStyle = "#244450";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, y0);
      ctx.lineTo(width, y0);
      ctx.stroke();
      ctx.fillStyle = "#7f9aa3";
      ctx.font = "11px sans-serif";
      ctx.fillText(ch, 8, index * 49 + 14);
      ctx.strokeStyle = COLORS[ch];
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      wave[ch].forEach((value, i) => {
        const x = (i / Math.max(1, wave[ch].length - 1)) * width;
        const y = y0 - Math.max(-20, Math.min(20, value / 6));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
  }, [wave]);
  return (
    <canvas
      ref={ref}
      className="signal-canvas"
      height="196"
      aria-label="실시간 4채널 뇌파 파형"
    />
  );
}

function TrendChart({
  trend,
}: {
  trend: Array<{
    t: number;
    engagement: number | null;
    workload: number | null;
    fatigue: number | null;
  }>;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const { ctx, width } = prepare(canvas, 144);
    const y = (v: number) => 72 - Math.max(-3, Math.min(3, v)) * 21;
    ctx.clearRect(0, 0, width, 144);
    ctx.strokeStyle = "#244450";
    ctx.lineWidth = 1;
    for (const tick of [-2, 0, 2]) {
      ctx.beginPath();
      ctx.moveTo(0, y(tick));
      ctx.lineTo(width, y(tick));
      ctx.stroke();
    }
    const lines: Array<["engagement" | "workload" | "fatigue", string]> = [
      ["engagement", "#5ab6dd"],
      ["workload", "#f0b567"],
      ["fatigue", "#ea83aa"],
    ];
    lines.forEach(([metric, color]) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      let started = false;
      trend.forEach((point, i) => {
        const value = point[metric];
        if (value === null) {
          started = false;
          return;
        }
        const x = trend.length < 2 ? 0 : (i / (trend.length - 1)) * width;
        if (started) ctx.lineTo(x, y(value));
        else ctx.moveTo(x, y(value));
        started = true;
      });
      ctx.stroke();
    });
  }, [trend]);
  return (
    <canvas
      ref={ref}
      className="signal-canvas"
      height="144"
      aria-label="휴식 대비 몰입, 부하, 피로 추이"
    />
  );
}

function headColor(value: number | null | undefined): string {
  if (value == null) return "#355260";
  const x = Math.max(-1, Math.min(1, value / 2));
  return x >= 0
    ? `rgb(${170 + 58 * x},${113 - 35 * x},${91 - 22 * x})`
    : `rgb(${83 + 15 * x},${150 + 11 * x},${165 - 58 * x})`;
}

export function LivePanels({
  snapshot,
  connected,
  wave,
  trend,
}: {
  snapshot: Snapshot | null;
  connected: boolean;
  wave: Record<Channel, number[]>;
  trend: Array<{
    t: number;
    engagement: number | null;
    workload: number | null;
    fatigue: number | null;
  }>;
}) {
  const [band, setBand] = useState<"alpha" | "theta" | "beta">("alpha");
  const quality = snapshot?.quality;
  const rel = snapshot?.rel;
  const z = snapshot?.z;
  return (
    <aside className="live-panel">
      <div className="telemetry-header">
        <div>
          <span className="eyebrow">실시간 측정</span>
          <h2>신호 관찰</h2>
        </div>
        <span className={`connection ${connected ? "online" : "offline"}`}>
          {connected ? "연결됨" : "연결 대기"}
        </span>
      </div>
      <div className="current-state">
        <span>현재 상태</span>
        <strong>{snapshot?.state_label || "측정 대기"}</strong>
        <small>
          {snapshot?.source
            ? `입력 ${snapshot.source.toUpperCase()} · ${Math.round(snapshot.t)}초`
            : "세션을 시작해 주세요"}
        </small>
      </div>
      <section className="telemetry-section">
        <h3>
          센서 접촉 <span>최근 10초</span>
        </h3>
        <div className="quality-grid">
          {CHANNELS.map((ch) => {
            const value = quality?.[ch] ?? 0;
            return (
              <div
                key={ch}
                className={`quality-cell ${value >= 0.7 ? "good" : value >= 0.4 ? "fair" : "poor"}`}
              >
                <b>{ch}</b>
                <span>{NAMES[ch]}</span>
                <strong>{quality ? `${Math.round(value * 100)}%` : "—"}</strong>
              </div>
            );
          })}
        </div>
        {snapshot?.quality_status === "poor" && (
          <p className="sensor-warning">
            센서가 피부에 잘 닿지 않았어요. 머리카락을 정리하고 다시 착용해
            주세요.
          </p>
        )}
      </section>
      <section className="telemetry-section">
        <h3>
          실시간 뇌파 <span>1–40 Hz · µV</span>
        </h3>
        <Waveform wave={wave} />
      </section>
      <section className="telemetry-section">
        <h3>
          휴식 대비 지표 <span>z 점수</span>
        </h3>
        <div className="metric-row">
          <span>몰입</span>
          <b>{z?.engagement == null ? "—" : z.engagement.toFixed(1)}</b>
          <span>작업 부하</span>
          <b>{z?.workload == null ? "—" : z.workload.toFixed(1)}</b>
          <span>피로</span>
          <b>{z?.fatigue == null ? "—" : z.fatigue.toFixed(1)}</b>
        </div>
        <TrendChart trend={trend} />
        <div className="legend">
          <span>몰입</span>
          <span>작업 부하</span>
          <span>피로</span>
        </div>
      </section>
      <section className="telemetry-section head-section">
        <h3>
          센서 위치별 활동
          <select
            aria-label="센서 지도 대역"
            value={band}
            onChange={(event) => setBand(event.target.value as typeof band)}
          >
            <option value="alpha">알파</option>
            <option value="theta">세타</option>
            <option value="beta">베타</option>
          </select>
        </h3>
        <svg
          viewBox="0 0 220 210"
          className="head-map"
          role="img"
          aria-label="네 센서 위치별 휴식 대비 변화"
        >
          <ellipse
            cx="110"
            cy="107"
            rx="89"
            ry="88"
            fill="none"
            stroke="#43616a"
            strokeWidth="2"
          />
          <path
            d="M100 20 L110 6 L120 20"
            fill="none"
            stroke="#43616a"
            strokeWidth="2"
          />
          {CHANNELS.map((ch) => {
            const [x, y] = POS[ch],
              value = snapshot?.head?.[ch]?.[band];
            return (
              <g key={ch}>
                <circle cx={x} cy={y} r="19" fill={headColor(value)} />
                <text
                  x={x}
                  y={y + 4}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize="10"
                >
                  {ch}
                </text>
                <text
                  x={x}
                  y={y + 32}
                  textAnchor="middle"
                  fill="#a7bac0"
                  fontSize="10"
                >
                  {value == null ? "—" : `${value > 0 ? "+" : ""}${value}`}
                </text>
              </g>
            );
          })}
        </svg>
        <p className="panel-note">
          점 4개는 센서 위치입니다. 색은 휴식 대비 변화이며 뇌 내부 위치를
          뜻하지 않습니다.
        </p>
      </section>
      <section className="telemetry-section">
        <h3>
          대역 구성 <span>상대 파워</span>
        </h3>
        {(["theta", "alpha", "beta"] as const).map((key) => (
          <div className="band-row" key={key}>
            <span>
              {key === "theta" ? "세타" : key === "alpha" ? "알파" : "베타"}
            </span>
            <div>
              <i
                style={{
                  width: `${Math.min(100, Math.max(0, (rel?.[key] ?? 0) * 100))}%`,
                }}
              />
            </div>
            <strong>
              {rel?.[key] == null ? "—" : `${Math.round(rel[key] * 100)}%`}
            </strong>
          </div>
        ))}
      </section>
    </aside>
  );
}
