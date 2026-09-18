import { useCallback, useEffect, useRef, useState } from "react";

export interface Segment {
  id: number;
  index: number;
  startMs: number;
  endMs: number;
}

export type PlayerState = "idle" | "playing-segment" | "playing-free" | "looping";
export type Speed = 0.75 | 1 | 1.25;

export interface AbLoop {
  aMs: number | null;
  bMs: number | null;
}

export interface UseSegmentPlayer {
  state: PlayerState;
  currentIndex: number;
  currentTimeMs: number;
  durationMs: number;
  speed: Speed;
  autoPause: boolean;
  loop: AbLoop;
  loopSentence: boolean;
  error: string | null;
  audioProps: { ref: React.RefObject<HTMLAudioElement | null>; src: string; preload: "auto" };
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  replaySentence: () => void;
  goToSegment: (index: number) => void;
  next: () => void;
  prev: () => void;
  seekMs: (ms: number) => void;
  setSpeed: (speed: Speed) => void;
  setAutoPause: (value: boolean) => void;
  setA: () => void;
  setB: () => void;
  clearLoop: () => void;
  toggleLoopSentence: () => void;
  retry: () => void;
}

/**
 * Bọc một <audio> duy nhất. Kiểm tra mốc thời gian bằng requestAnimationFrame khi đang phát
 * (độ lệch ≤ 100 ms, NFR-03), và chỉ khi tab đang hiển thị (Safari iOS throttle rAF).
 */
export function useSegmentPlayer(audioUrl: string, segments: Segment[], initialIndex = 0): UseSegmentPlayer {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const [state, setState] = useState<PlayerState>("idle");
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [speed, setSpeedState] = useState<Speed>(1);
  const [autoPause, setAutoPause] = useState(true);
  const [loop, setLoop] = useState<AbLoop>({ aMs: null, bMs: null });
  const [loopSentence, setLoopSentence] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const segment = segments[currentIndex];

  const stopRaf = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
  };

  const pause = useCallback(() => {
    audioRef.current?.pause();
    stopRaf();
    setState("idle");
  }, []);

  /** Vòng kiểm mốc: A-B loop ưu tiên, sau đó auto-pause cuối câu. */
  const tick = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const ms = audio.currentTime * 1000;
    setCurrentTimeMs(ms);

    const { aMs, bMs } = loop;
    if (aMs !== null && bMs !== null && ms >= bMs) {
      audio.currentTime = aMs / 1000;
    } else if (loopSentence && segment && ms >= segment.endMs) {
      audio.currentTime = segment.startMs / 1000;
    } else if (autoPause && segment && ms >= segment.endMs) {
      audio.pause();
      audio.currentTime = segment.endMs / 1000;
      stopRaf();
      setState("idle");
      return; // trả focus về ô nhập do workspace xử lý
    } else if (segment && ms > segment.endMs) {
      const nextIdx = segments.findIndex((s) => ms < s.endMs);
      if (nextIdx > -1 && nextIdx !== currentIndex) setCurrentIndex(nextIdx);
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [autoPause, currentIndex, loop, loopSentence, segment, segments]);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = speed;
    audio.preservesPitch = true;
    void audio
      .play()
      .then(() => {
        setError(null);
        setState(loop.aMs !== null && loop.bMs !== null ? "looping" : autoPause ? "playing-segment" : "playing-free");
        stopRaf();
        rafRef.current = requestAnimationFrame(tick);
      })
      .catch(() => setError("Không tải được audio"));
  }, [autoPause, loop.aMs, loop.bMs, speed, tick]);

  const seekMs = useCallback((ms: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = ms / 1000;
    setCurrentTimeMs(ms);
  }, []);

  const goToSegment = useCallback(
    (index: number) => {
      const target = segments[Math.max(0, Math.min(segments.length - 1, index))];
      if (!target) return;
      setCurrentIndex(target.index);
      seekMs(target.startMs);
    },
    [seekMs, segments],
  );

  const replaySentence = useCallback(() => {
    if (!segment) return;
    seekMs(segment.startMs);
    play();
  }, [play, seekMs, segment]);

  // pause khi tab bị ẩn: rAF bị throttle → mốc auto-pause sẽ lệch
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) pause();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [pause]);

  useEffect(() => stopRaf, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.playbackRate = speed;
  }, [speed]);

  return {
    state,
    currentIndex,
    currentTimeMs,
    durationMs,
    speed,
    autoPause,
    loop,
    loopSentence,
    error,
    audioProps: { ref: audioRef, src: audioUrl, preload: "auto" },
    play,
    pause,
    togglePlay: () => (state === "idle" ? play() : pause()),
    replaySentence,
    goToSegment,
    next: () => goToSegment(currentIndex + 1),
    prev: () => goToSegment(currentIndex - 1),
    seekMs,
    setSpeed: setSpeedState,
    setAutoPause,
    setA: () => setLoop((l) => normalizeLoop({ ...l, aMs: currentTimeMs })),
    setB: () => setLoop((l) => normalizeLoop({ ...l, bMs: currentTimeMs })),
    clearLoop: () => setLoop({ aMs: null, bMs: null }),
    toggleLoopSentence: () => setLoopSentence((v) => !v),
    retry: () => {
      setError(null);
      audioRef.current?.load();
    },
  };
}

/** B < A thì đổi chỗ (AC player). */
function normalizeLoop(loop: AbLoop): AbLoop {
  const { aMs, bMs } = loop;
  if (aMs !== null && bMs !== null && bMs < aMs) return { aMs: bMs, bMs: aMs };
  return loop;
}
