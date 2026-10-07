import type {
  ActivityChoice,
  ActivityResult,
  BrainType,
  LiveResult,
  Snapshot,
  SourceKind,
  TrialPayload,
} from "./types";

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : `요청 실패 (${response.status})`,
    );
  return payload as T;
}

export const liveApi = {
  start: (options: {
    source: SourceKind;
    replay_path?: string;
    user: string;
    n_activities: number;
    record_markers: boolean;
  }) => request<{ session_id: string }>("/api/live/start", options),
  phase: (phase: string) =>
    request<{ phase: string }>("/api/live/phase", { phase }),
  mark: (event: string, attrs: Record<string, string | number> = {}) =>
    request<{
      t: number;
      brain_type?: BrainType;
      activity_result?: ActivityResult;
    }>("/api/live/mark", { event, attrs }),
  trial: (trial: TrialPayload) =>
    request<{ ok: boolean }>("/api/live/trial", trial),
  next: () =>
    request<ActivityChoice | { activity: null; reason: string }>(
      "/api/live/next",
    ),
  status: () => request<Snapshot>("/api/live/status"),
  finish: () => request<LiveResult>("/api/live/finish", {}),
};
