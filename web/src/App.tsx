import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useReducer,
  useState,
} from "react";
import { ActivityRunner } from "./activities/ActivityRunner";
import { liveApi } from "./api";
import { restSeconds } from "./flow";
import type { MeasurementMode } from "./flow";
import { LivePanels } from "./LivePanels";
import type {
  ActivityChoice,
  ActivityResult,
  BrainType,
  LiveResult,
  SourceKind,
  TrialPayload,
} from "./types";
import { useLiveSocket } from "./useLiveSocket";
import "./styles.css";

const Results = lazy(() =>
  import("./Results").then((module) => ({ default: module.Results })),
);

type Screen =
  | "setup"
  | "recover"
  | "signal"
  | "baseline_eo"
  | "baseline_ec"
  | "brain_type"
  | "activity_intro"
  | "activity_running"
  | "activity_summary"
  | "analyzing"
  | "results"
  | "error";
type FlowState = {
  screen: Screen;
  busy: boolean;
  error: string | null;
  brainType: BrainType | null;
  choice: ActivityChoice | null;
  block: number;
  lastActivity: ActivityResult | null;
  result: LiveResult | null;
};
type FlowAction = { type: "update"; patch: Partial<FlowState> };
const initial: FlowState = {
  screen: sessionStorage.getItem("brainfit-live-active") ? "recover" : "setup",
  busy: false,
  error: null,
  brainType: null,
  choice: null,
  block: 0,
  lastActivity: null,
  result: null,
};
function reducer(state: FlowState, action: FlowAction): FlowState {
  return { ...state, ...action.patch };
}
const delay = (ms: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, ms));

export default function App() {
  const [flow, dispatch] = useReducer(reducer, initial);
  const update = (patch: Partial<FlowState>) =>
    dispatch({ type: "update", patch });
  const [source, setSource] = useState<SourceKind>("sim");
  const [replayPath, setReplayPath] = useState("data/demo/synthetic_demo.npz");
  const [user, setUser] = useState("demo");
  const [mode, setMode] = useState<MeasurementMode>("demo");
  const [activityCount, setActivityCount] = useState(4);
  const [recordMarkers, setRecordMarkers] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [restRemaining, setRestRemaining] = useState(0);
  const { snapshot, connected, wave, trend, qualityReady, clear } =
    useLiveSocket();

  useEffect(() => {
    if (flow.screen !== "activity_summary" || restRemaining <= 0) return;
    const timer = window.setTimeout(() => setRestRemaining((n) => n - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [flow.screen, restRemaining]);

  const fail = (error: unknown) =>
    update({
      screen: "error",
      busy: false,
      error:
        error instanceof Error ? error.message : "요청을 처리하지 못했습니다.",
    });

  const start = async () => {
    if (!/^[A-Za-z0-9_-]{1,32}$/.test(user)) {
      update({
        error: "사용자 ID는 영문·숫자·밑줄·하이픈 1–32자로 입력해 주세요.",
      });
      return;
    }
    update({ busy: true, error: null });
    try {
      await liveApi.start({
        source,
        replay_path: source === "replay" ? replayPath : undefined,
        user,
        n_activities: activityCount,
        record_markers: recordMarkers,
      });
      await liveApi.phase("signal_check");
      sessionStorage.setItem("brainfit-live-active", "1");
      clear();
      update({
        screen: "signal",
        busy: false,
        brainType: null,
        choice: null,
        block: 0,
        lastActivity: null,
        result: null,
      });
    } catch (error) {
      fail(error);
    }
  };

  const countDown = async (seconds: number) => {
    for (let n = seconds; n > 0; n--) {
      setRemaining(n);
      await delay(1000);
    }
    setRemaining(0);
  };
  const beep = () => {
    try {
      const context = new AudioContext(),
        oscillator = context.createOscillator();
      oscillator.frequency.value = 880;
      oscillator.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.3);
      oscillator.onended = () => {
        void context.close();
      };
    } catch {
      /* 소리가 지원되지 않아도 측정을 계속한다. */
    }
  };
  const beginBaseline = async () => {
    if (flow.busy) return;
    update({ busy: true, error: null });
    try {
      await liveApi.mark("rest_eo_start");
      update({ screen: "baseline_eo" });
      await countDown(restSeconds(mode));
      await liveApi.mark("rest_eo_end");
      await liveApi.mark("rest_ec_start");
      update({ screen: "baseline_ec" });
      await countDown(restSeconds(mode));
      beep();
      const response = await liveApi.mark("rest_ec_end");
      update({
        screen: "brain_type",
        busy: false,
        brainType: response.brain_type ?? null,
      });
    } catch (error) {
      fail(error);
    }
  };

  const finish = async () => {
    update({ screen: "analyzing", busy: true });
    try {
      const result = await liveApi.finish();
      sessionStorage.removeItem("brainfit-live-active");
      update({ screen: "results", busy: false, result });
    } catch (error) {
      fail(error);
    }
  };
  const loadNext = async () => {
    update({ busy: true });
    try {
      const next = await liveApi.next();
      if (next.activity === null) {
        await finish();
        return;
      }
      update({ screen: "activity_intro", busy: false, choice: next });
    } catch (error) {
      fail(error);
    }
  };
  const startActivity = async () => {
    if (!flow.choice || flow.busy) return;
    update({ busy: true });
    const block = flow.block + 1;
    try {
      await liveApi.mark("block_start", { task: flow.choice.task, block });
      update({ screen: "activity_running", busy: false, block });
    } catch (error) {
      fail(error);
    }
  };
  const sendTrial = useCallback(async (trial: TrialPayload) => {
    const result = await liveApi.trial(trial);
    if (!result.ok) throw new Error("시행 기록을 저장하지 못했습니다.");
  }, []);
  const completeActivity = async () => {
    if (!flow.choice) return;
    try {
      const response = await liveApi.mark("block_end", {
        task: flow.choice.task,
        block: flow.block,
      });
      setRestRemaining(5);
      update({
        screen: "activity_summary",
        lastActivity: response.activity_result ?? null,
      });
    } catch (error) {
      fail(error);
    }
  };
  const restart = () => {
    sessionStorage.removeItem("brainfit-live-active");
    update({
      screen: "setup",
      busy: false,
      error: null,
      brainType: null,
      choice: null,
      block: 0,
      result: null,
    });
  };

  const stages = ["시작", "착용 확인", "기준선", "활동", "결과"];
  const currentStep =
    flow.screen === "setup" || flow.screen === "recover"
      ? 0
      : flow.screen === "signal"
        ? 1
        : flow.screen.startsWith("baseline") || flow.screen === "brain_type"
          ? 2
          : flow.screen === "results"
            ? 4
            : 3;
  const showLivePanel = [
    "signal",
    "baseline_eo",
    "baseline_ec",
    "brain_type",
    "activity_intro",
    "activity_running",
    "activity_summary",
  ].includes(flow.screen);

  return (
    <div className={`app-shell ${largeText ? "large-text" : ""}`}>
      <header className="app-header">
        <div className="brand">
          <strong>
            BrainFit <em>live</em>
          </strong>
        </div>
        <div className="header-actions">
          <button
            className="text-toggle"
            onClick={() => setLargeText((value) => !value)}
            aria-pressed={largeText}
          >
            큰 글씨 {largeText ? "끄기" : "켜기"}
          </button>
        </div>
      </header>
      <nav className="step-nav" aria-label="측정 단계">
        {stages.map((name, i) => (
          <div
            key={name}
            className={
              i === currentStep ? "current" : i < currentStep ? "done" : ""
            }
          >
            <span>{i + 1}</span>
            {name}
          </div>
        ))}
      </nav>
      <div className={`workspace ${showLivePanel ? "" : "solo-workspace"}`}>
        <main className="task-panel">
          {flow.error && flow.screen !== "error" && (
            <div className="error-banner" role="alert">
              {flow.error}
            </div>
          )}
          {flow.screen === "setup" && (
            <section className="start-screen">
              <span className="eyebrow">측정 시작</span>
              <h1>
                지금의 집중 흐름을
                <br />
                확인해 볼까요?
              </h1>
              <p>
                눈 뜬·감은 휴식으로 기준선을 만든 다음, 인지 활동을 직접
                수행합니다. 활동 중 변화는 오른쪽에 실시간으로 표시됩니다.
              </p>
              <div className="form-grid">
                <label>
                  입력 신호
                  <select
                    value={source}
                    onChange={(event) =>
                      setSource(event.target.value as SourceKind)
                    }
                  >
                    <option value="sim">시뮬레이터 — 장비 없이 체험</option>
                    <option value="lsl">Muse 2 — BlueMuse 연결</option>
                    <option value="replay">녹화 재생</option>
                  </select>
                </label>
                {source === "replay" && (
                  <label>
                    재생 파일 경로
                    <input
                      value={replayPath}
                      onChange={(event) => setReplayPath(event.target.value)}
                    />
                  </label>
                )}
                <label>
                  사용자 ID
                  <input
                    value={user}
                    onChange={(event) => setUser(event.target.value)}
                    maxLength={32}
                  />
                </label>
                <label>
                  측정 모드
                  <select
                    value={mode}
                    onChange={(event) =>
                      setMode(event.target.value as MeasurementMode)
                    }
                  >
                    <option value="demo">시연 — 휴식 각 30초</option>
                    <option value="standard">정식 — 휴식 각 60초</option>
                  </select>
                </label>
                <label>
                  활동 수
                  <select
                    value={activityCount}
                    onChange={(event) =>
                      setActivityCount(Number(event.target.value))
                    }
                  >
                    <option value={3}>3개</option>
                    <option value={4}>4개</option>
                    <option value={5}>5개</option>
                  </select>
                </label>
              </div>
              {source === "lsl" && (
                <label className="marker-option">
                  <input
                    type="checkbox"
                    checked={recordMarkers}
                    onChange={(event) => setRecordMarkers(event.target.checked)}
                  />{" "}
                  LabRecorder에 활동 마커도 기록
                </label>
              )}
              <button
                className="primary start-button"
                onClick={start}
                disabled={flow.busy}
              >
                뇌파 테스트 시작
              </button>
              <p className="disclaimer">
                학습·훈련용 참고 지표이며 의학적 진단이 아닙니다.
              </p>
            </section>
          )}
          {flow.screen === "recover" && (
            <section className="center-screen">
              <span className="eyebrow">진행 중이던 세션</span>
              <h1>화면이 새로고침되었습니다</h1>
              <p>
                진행 중이던 화면 단계는 복구할 수 없습니다. 새 측정을 시작하면
                이전 세션이 대체됩니다.
              </p>
              <button className="primary" onClick={restart}>
                새 측정 설정하기
              </button>
            </section>
          )}
          {flow.screen === "signal" && (
            <section className="center-screen">
              <span className="eyebrow">착용 확인</span>
              <h1>센서 네 곳을 확인해 주세요</h1>
              <p>
                모든 센서의 깨끗한 구간이 70% 이상으로 3초간 유지되면 다음으로
                진행합니다.
              </p>
              <div className={`readiness ${qualityReady ? "ready" : ""}`}>
                {qualityReady ? "신호가 안정되었습니다" : "센서 접촉 확인 중"}
              </div>
              <button
                className="primary"
                disabled={!qualityReady || flow.busy}
                onClick={beginBaseline}
              >
                기준선 측정 시작
              </button>
            </section>
          )}
          {(flow.screen === "baseline_eo" || flow.screen === "baseline_ec") && (
            <section className="center-screen baseline-screen">
              <span className="eyebrow">
                기준선 {flow.screen === "baseline_eo" ? "1 / 2" : "2 / 2"}
              </span>
              <h1>
                {flow.screen === "baseline_eo"
                  ? "눈을 뜨고 편하게 쉬세요"
                  : "눈을 감고 쉬세요"}
              </h1>
              <div className="rest-focus" aria-hidden="true">
                {flow.screen === "baseline_eo" ? "+" : "◌"}
              </div>
              <strong className="timer">
                {remaining}
                <small>초 남음</small>
              </strong>
              <p>
                {flow.screen === "baseline_eo"
                  ? "화면 가운데를 바라보며 편하게 호흡하세요."
                  : "소리가 나면 눈을 뜨세요."}
              </p>
            </section>
          )}
          {flow.screen === "brain_type" && (
            <section className="center-screen type-screen">
              <span className="eyebrow">기준선 분석 완료</span>
              <h1>오늘의 뇌파 성향</h1>
              <div className="brain-type-name">
                {flow.brainType?.name || "측정 완료"}
              </div>
              <p>{flow.brainType?.summary}</p>
              <div className="tip">{flow.brainType?.tip}</div>
              <p className="panel-note">
                임시 참고 기준에 따른 오늘의 상태이며 성격이나 능력 판단이
                아닙니다.
              </p>
              <button
                className="primary"
                disabled={flow.busy}
                onClick={loadNext}
              >
                첫 활동 보기
              </button>
            </section>
          )}
          {flow.screen === "activity_intro" && flow.choice && (
            <section className="center-screen activity-intro">
              <span className="eyebrow">
                활동 {flow.choice.index} / {flow.choice.total}
              </span>
              <h1>{flow.choice.name}</h1>
              <p className="activity-how">{flow.choice.how}</p>
              <div className="choice-reason">
                <span>이 활동을 선택한 이유</span>
                <p>{flow.choice.reason}</p>
              </div>
              <button
                className="primary"
                disabled={flow.busy}
                onClick={startActivity}
              >
                활동 시작
              </button>
            </section>
          )}
          {flow.screen === "activity_running" && flow.choice && (
            <ActivityRunner
              key={flow.block}
              choice={flow.choice}
              block={flow.block}
              onTrial={sendTrial}
              onDone={completeActivity}
              onError={(message) => fail(new Error(message))}
            />
          )}
          {flow.screen === "activity_summary" && (
            <section className="center-screen activity-summary">
              <span className="eyebrow">활동 {flow.block} 완료</span>
              <h1>{flow.lastActivity?.name || flow.choice?.name}</h1>
              <div className="summary-state">
                {flow.lastActivity?.responsive === null
                  ? "판단 보류"
                  : flow.lastActivity?.responsive
                    ? "뇌파 반응이 뚜렷했어요"
                    : "뇌파 반응이 약했어요"}
              </div>
              <div className="summary-numbers">
                <div>
                  몰입 변화
                  <strong>{flow.lastActivity?.z?.engagement ?? "—"}</strong>
                </div>
                <div>
                  작업 부하
                  <strong>{flow.lastActivity?.z?.workload ?? "—"}</strong>
                </div>
                <div>
                  정확도
                  <strong>
                    {flow.lastActivity?.behavior?.accuracy == null
                      ? "—"
                      : `${Math.round(flow.lastActivity.behavior.accuracy * 100)}%`}
                  </strong>
                </div>
              </div>
              {flow.lastActivity?.feedback.map((line) => (
                <p className="feedback" key={line}>
                  {line}
                </p>
              ))}
              <button
                className="primary"
                disabled={restRemaining > 0 || flow.busy}
                onClick={loadNext}
              >
                {restRemaining > 0
                  ? `잠깐 쉬어요 · ${restRemaining}초`
                  : "다음 활동 보기"}
              </button>
            </section>
          )}
          {flow.screen === "analyzing" && (
            <section className="center-screen">
              <span className="eyebrow">측정 완료</span>
              <h1>결과를 정리하고 있어요</h1>
            </section>
          )}
          {flow.screen === "results" && flow.result && (
            <Suspense
              fallback={
                <section className="center-screen">
                  <h1>결과 화면을 여는 중입니다</h1>
                </section>
              }
            >
              <Results result={flow.result} onRestart={restart} />
            </Suspense>
          )}
          {flow.screen === "error" && (
            <section className="center-screen">
              <span className="eyebrow">진행 중단</span>
              <h1>측정을 계속할 수 없습니다</h1>
              <p role="alert">{flow.error}</p>
              <button className="primary" onClick={restart}>
                새 측정 시작하기
              </button>
            </section>
          )}
        </main>
        {showLivePanel && (
          <LivePanels
            snapshot={snapshot}
            connected={connected}
            wave={wave}
            trend={trend}
          />
        )}
      </div>
      <footer>
        BrainFit · 학습·훈련용 참고 지표 · 의학적 진단이 아닙니다.
      </footer>
    </div>
  );
}
