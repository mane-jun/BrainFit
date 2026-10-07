export type SourceKind = "sim" | "lsl" | "replay";
export type ActivityId =
  | "gonogo"
  | "nback"
  | "oddball"
  | "stroop"
  | "arithmetic"
  | "pvt"
  | "word_memory";
export type Channel = "TP9" | "AF7" | "AF8" | "TP10";
export const CHANNELS: Channel[] = ["TP9", "AF7", "AF8", "TP10"];

export interface ActivityChoice {
  activity: ActivityId;
  task: string;
  level: number | null;
  name: string;
  how: string;
  sec: number;
  mode: "explore" | "compensate" | "hold";
  reason: string;
  index: number;
  total: number;
}

export interface TrialPayload {
  task: string;
  block: number;
  idx: number;
  target: number;
  resp: number;
  correct: number;
  rt: number;
  extra?: Record<string, string | number | boolean>;
}

export interface BrainType {
  id: string;
  name: string;
  summary: string;
  tip: string;
  notes?: string[];
  disclaimer?: string;
}

export interface Snapshot {
  t: number;
  phase: string;
  activity: string | null;
  source: SourceKind;
  quality: Record<Channel, number>;
  quality_status: "good" | "fair" | "poor";
  rel: Record<string, number> | null;
  head: Record<Channel, Record<string, number | null>> | null;
  z: Record<"engagement" | "workload" | "fatigue", number | null> | null;
  state_label: string;
  brain_type: BrainType | null;
  baseline_ready: boolean;
}

export interface LiveTick {
  type: "tick";
  snapshot: Snapshot;
  wave: { sfreq: number; ch: Channel[]; data: number[][] };
}

export interface ActivityResult {
  activity: ActivityId;
  name: string;
  task: string;
  block: number;
  responsive: boolean | null;
  z: Record<"engagement" | "workload" | "fatigue", number> | null;
  behavior?: {
    n_trials: number;
    accuracy: number;
    fa_rate?: number;
    miss_rate?: number;
    rt_median?: number;
  };
  feedback: string[];
}

export interface LiveResult {
  session_id: string;
  brain_type: BrainType | null;
  activities: ActivityResult[];
  overall: {
    message: string;
    most_focused?: string;
    least_focused?: string;
    fast_decline?: string[];
  };
  report?: {
    profile?: {
      axes?: Record<string, { ko: string; score: number | null }>;
      reference_note?: string;
    };
  };
  figures?: string[];
  report_error?: string;
}
