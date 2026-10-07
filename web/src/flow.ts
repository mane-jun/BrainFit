import type { Channel } from "./types";
import { CHANNELS } from "./types";

export type MeasurementMode = "demo" | "standard";

export function allSensorsGood(
  quality: Record<Channel, number> | null | undefined,
): boolean {
  return Boolean(
    quality && CHANNELS.every((channel) => quality[channel] >= 0.7),
  );
}

export function restSeconds(mode: MeasurementMode): number {
  return mode === "demo" ? 30 : 60;
}

export function responseLabel(responsive: boolean | null): string {
  return responsive === null
    ? "판단 보류"
    : responsive
      ? "반응 뚜렷"
      : "반응 약함";
}
