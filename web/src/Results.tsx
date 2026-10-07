import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ActivityResult, LiveResult } from "./types";
import { responseLabel } from "./flow";

function ActivityCard({ activity }: { activity: ActivityResult }) {
  return (
    <article className="result-activity">
      <div className="result-activity-head">
        <h3>{activity.name}</h3>
        <span
          className={`response-state ${activity.responsive === null ? "unknown" : activity.responsive ? "strong" : "weak"}`}
        >
          {responseLabel(activity.responsive)}
        </span>
      </div>
      <div className="result-metrics">
        <div>
          <span>몰입 변화</span>
          <strong>
            {activity.z?.engagement == null
              ? "—"
              : `${activity.z.engagement > 0 ? "+" : ""}${activity.z.engagement.toFixed(1)}`}
          </strong>
        </div>
        <div>
          <span>작업 부하</span>
          <strong>
            {activity.z?.workload == null
              ? "—"
              : `${activity.z.workload > 0 ? "+" : ""}${activity.z.workload.toFixed(1)}`}
          </strong>
        </div>
        <div>
          <span>정확도</span>
          <strong>
            {activity.behavior?.accuracy == null
              ? "—"
              : `${Math.round(activity.behavior.accuracy * 100)}%`}
          </strong>
        </div>
      </div>
      {activity.feedback.length > 0 && (
        <p className="feedback">{activity.feedback.join(" ")}</p>
      )}
    </article>
  );
}

export function Results({
  result,
  onRestart,
}: {
  result: LiveResult;
  onRestart: () => void;
}) {
  const profile = result.report?.profile;
  const radar = Object.values(profile?.axes ?? {})
    .filter((axis) => axis.score !== null)
    .map((axis) => ({ name: axis.ko, score: axis.score }));
  const bars = result.activities.map((activity) => ({
    name: activity.name,
    engagement: activity.z?.engagement ?? null,
  }));
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `brainfit-${result.session_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="results-view">
      <span className="eyebrow">측정 완료</span>
      <h2>오늘의 측정 결과</h2>
      <p className="result-overall">{result.overall.message}</p>
      {result.brain_type && (
        <div className="result-type">
          <span>오늘의 뇌파 성향</span>
          <strong>{result.brain_type.name}</strong>
          <p>{result.brain_type.summary}</p>
        </div>
      )}
      {bars.some((bar) => bar.engagement !== null) && (
        <div className="result-chart">
          <h3>활동별 몰입 변화</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart
              data={bars}
              margin={{ top: 12, right: 8, bottom: 18, left: -25 }}
            >
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis
                dataKey="name"
                tick={{ fill: "var(--muted)", fontSize: 11 }}
                interval={0}
                angle={-12}
                textAnchor="end"
              />
              <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  borderColor: "var(--line)",
                  color: "var(--ink)",
                }}
              />
              <Bar dataKey="engagement" name="몰입 z" fill="var(--chart-bar)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="activity-results">
        <h3>활동별 기록</h3>
        {result.activities.map((activity) => (
          <ActivityCard
            key={`${activity.task}-${activity.block}`}
            activity={activity}
          />
        ))}
      </div>
      {radar.length > 2 && (
        <div className="result-chart">
          <h3>Brain Profile</h3>
          <p className="panel-note">
            점수 기준값은 임시값입니다. 능력 점수는 과제 수행 성과를 바탕으로
            합니다.
          </p>
          <ResponsiveContainer width="100%" height={310}>
            <RadarChart data={radar} outerRadius="70%">
              <PolarGrid stroke="var(--chart-grid)" />
              <PolarAngleAxis
                dataKey="name"
                tick={{ fill: "var(--muted)", fontSize: 12 }}
              />
              <Radar
                dataKey="score"
                stroke="var(--chart-label)"
                fill="var(--chart-bar)"
                fillOpacity={0.2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}
      {result.figures && result.figures.length > 0 && (
        <details className="report-gallery">
          <summary>상세 분석 그림 {result.figures.length}장 보기</summary>
          <div>
            {result.figures.map((url) => (
              <img
                key={url}
                src={url}
                alt={decodeURIComponent(url.split("/").at(-1) || "분석 그림")}
                loading="lazy"
              />
            ))}
          </div>
        </details>
      )}
      {result.report_error && (
        <p className="soft-warning">
          상세 분석 그림을 만들 수 없었습니다: {result.report_error}
        </p>
      )}
      <div className="result-actions">
        <button onClick={download}>결과 JSON 내려받기</button>
        <button className="primary" onClick={onRestart}>
          새 측정 시작
        </button>
      </div>
      <p className="disclaimer">
        본 결과는 학습·훈련용 참고 지표이며 의학적 진단이 아닙니다.
      </p>
    </div>
  );
}
