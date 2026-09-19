import { useCallback, useEffect, useRef, useState } from "react";

/** Plays one [start, end] span of an audio file; stops at `end` (checked every frame). */
export function useClipPlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);

  const stop = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    audioRef.current?.pause();
    setPlayingId(null);
  }, []);

  const play = useCallback(
    (id: number, startMs: number, endMs: number) => {
      const audio = audioRef.current;
      if (!audio) return;
      stop();
      audio.currentTime = startMs / 1000;
      const watch = () => {
        if (audio.currentTime * 1000 >= endMs) {
          stop();
          return;
        }
        rafRef.current = requestAnimationFrame(watch);
      };
      void audio.play().then(() => {
        setPlayingId(id);
        rafRef.current = requestAnimationFrame(watch);
      });
    },
    [stop],
  );

  useEffect(() => stop, [stop]);

  return { audioRef, playingId, play, stop };
}
