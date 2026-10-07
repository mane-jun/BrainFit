import { useEffect, useState } from "react";
import type { Channel, LiveTick, Snapshot } from "./types";
import { CHANNELS } from "./types";
import { allSensorsGood } from "./flow";
import { useRef } from "react";

export function useLiveSocket() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [wave, setWave] = useState<Record<Channel, number[]>>({
    TP9: [],
    AF7: [],
    AF8: [],
    TP10: [],
  });
  const [trend, setTrend] = useState<
    Array<{
      t: number;
      engagement: number | null;
      workload: number | null;
      fatigue: number | null;
    }>
  >([]);
  const [qualityReady, setQualityReady] = useState(false);
  const qualitySince = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      if (!active) return;
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/ws/live`);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event: MessageEvent<string>) => {
        let message: LiveTick | { type: "idle" };
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        if (message.type !== "tick") return;
        setSnapshot(message.snapshot);
        if (allSensorsGood(message.snapshot.quality)) {
          if (qualitySince.current === null)
            qualitySince.current = performance.now();
          setQualityReady(performance.now() - qualitySince.current >= 3000);
        } else {
          qualitySince.current = null;
          setQualityReady(false);
        }
        setWave((previous) => {
          const next = { ...previous };
          CHANNELS.forEach((channel, i) => {
            const index = message.wave.ch.indexOf(channel);
            next[channel] = [
              ...previous[channel],
              ...(message.wave.data[index >= 0 ? index : i] ?? []),
            ].slice(-message.wave.sfreq * 5);
          });
          return next;
        });
        if (message.snapshot.z)
          setTrend((previous) =>
            [
              ...previous,
              {
                t: message.snapshot.t,
                ...message.snapshot.z!,
              },
            ].slice(-240),
          );
      };
      socket.onclose = () => {
        setConnected(false);
        qualitySince.current = null;
        setQualityReady(false);
        if (active) retry = setTimeout(connect, 1000);
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => {
      active = false;
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, []);

  function clear() {
    setWave({ TP9: [], AF7: [], AF8: [], TP10: [] });
    setTrend([]);
    qualitySince.current = null;
    setQualityReady(false);
  }
  return { snapshot, connected, wave, trend, qualityReady, clear };
}
