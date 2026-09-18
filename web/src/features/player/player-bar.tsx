import clsx from "clsx";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { SHORTCUT_HELP } from "../dictation/shortcuts";
import type { Segment, Speed, UseSegmentPlayer } from "./use-segment-player";

const SPEEDS: Speed[] = [0.75, 1, 1.25];

const mmss = (ms: number) => {
  const total = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
};

interface PlayerBarProps {
  player: UseSegmentPlayer;
  segments: Segment[];
  /** "Đã lưu" / "Chưa lưu" cho autosave ngoại tuyến. */
  saveState: "saved" | "pending" | "offline";
}

/** Thanh player dính trên đầu workspace: nút, tốc độ, A-B, tự dừng, thanh tiến độ theo câu. */
export function PlayerBar({ player, segments, saveState }: PlayerBarProps) {
  const total = segments.at(-1)?.endMs ?? player.durationMs;
  const pct = (ms: number) => (total ? (ms / total) * 100 : 0);
  const { aMs, bMs } = player.loop;
  const loopActive = aMs !== null && bMs !== null;

  return (
    <div className="sticky top-0 z-10 flex flex-col gap-3 border-b border-line bg-surface px-5 pb-3.5 pt-4">
      <audio {...player.audioProps} className="hidden" />

      {player.error && (
        <div className="flex items-center gap-3 rounded-xl border border-bad bg-bad-soft px-4 py-3">
          <span className="text-sm font-semibold text-bad">Không tải được audio</span>
          <span className="text-[13px] text-ink-2">Kiểm tra kết nối rồi thử lại. Bạn vẫn gõ được câu đang mở.</span>
          <Button size="sm" className="ml-auto" onClick={player.retry}>
            Thử lại
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" aria-label="Câu trước (Ctrl+,)" onClick={player.prev}>
            ◀◀
          </Button>
          <Button
            size="icon"
            className="size-11 rounded-full"
            aria-label="Phát hoặc tạm dừng (Ctrl+')"
            onClick={player.togglePlay}
          >
            {player.state === "idle" ? "▶" : "❚❚"}
          </Button>
          <Button variant="outline" size="icon" aria-label="Câu sau (Ctrl+.)" onClick={player.next}>
            ▶▶
          </Button>
          <Button variant="outline" size="sm" onClick={player.replaySentence}>
            ↻ Phát lại câu <kbd className="ml-1.5 font-mono text-[11px] text-ink-3">Ctrl+↵</kbd>
          </Button>
        </div>

        <ToggleGroup
          type="single"
          value={String(player.speed)}
          onValueChange={(v) => v && player.setSpeed(Number(v) as Speed)}
          aria-label="Tốc độ phát"
          className="rounded-[9px] border border-line bg-surface-2 p-0.5"
        >
          {SPEEDS.map((s) => (
            <ToggleGroupItem key={s} value={String(s)} className="h-[30px] px-3 text-xs">
              {s}x
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        <div className="flex items-center gap-1.5 rounded-[9px] border border-line bg-surface-2 py-0.5 pl-2.5 pr-0.5">
          <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-ink-3">Lặp A-B</span>
          <Button
            variant={aMs !== null ? "default" : "ghost"}
            size="sm"
            onClick={player.setA}
            aria-pressed={aMs !== null}
          >
            A
          </Button>
          <Button
            variant={bMs !== null ? "default" : "ghost"}
            size="sm"
            onClick={player.setB}
            aria-pressed={bMs !== null}
          >
            B
          </Button>
          <Button variant="ghost" size="sm" onClick={player.clearLoop} disabled={!aMs && !bMs}>
            Xoá
          </Button>
        </div>

        <Button
          variant="outline"
          size="sm"
          aria-pressed={player.loopSentence}
          className={clsx(player.loopSentence && "border-accent bg-accent-soft text-accent-ink")}
          onClick={player.toggleLoopSentence}
        >
          ⟲ Lặp câu này
        </Button>

        <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
          Tự dừng cuối câu
          <Switch checked={player.autoPause} onCheckedChange={player.setAutoPause} aria-label="Tự dừng cuối câu" />
        </label>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" className="rounded-full" aria-label="Phím tắt">
              ⌘
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">Phím tắt</p>
            <ul className="flex flex-col gap-1.5">
              {SHORTCUT_HELP.map((s) => (
                <li key={s.keys} className="flex justify-between gap-3 text-[13px] text-ink-2">
                  <span>{s.action}</span>
                  <kbd className="font-mono text-xs text-ink">{s.keys}</kbd>
                </li>
              ))}
            </ul>
          </PopoverContent>
        </Popover>
      </div>

      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-ink-3">{mmss(player.currentTimeMs)}</span>
        <div className="relative flex h-[22px] flex-1 items-center gap-0.5" role="group" aria-label="Tiến độ theo câu">
          {segments.map((s) => {
            const done = s.index < player.currentIndex;
            const current = s.index === player.currentIndex;
            return (
              <button
                key={s.id}
                type="button"
                title={`Câu ${s.index + 1}`}
                aria-label={`Đến câu ${s.index + 1}`}
                aria-current={current}
                onClick={() => player.goToSegment(s.index)}
                className={clsx(
                  "flex-1 rounded-[3px] transition-[height]",
                  current ? "h-[18px] bg-accent" : done ? "h-2.5 bg-ok" : "h-2.5 bg-line-2 opacity-55",
                )}
              />
            );
          })}
          {loopActive && (
            <div
              aria-hidden
              className="pointer-events-none absolute top-0.5 h-[18px] rounded border border-accent bg-accent/15"
              style={{ left: `${pct(aMs)}%`, width: `${pct(bMs) - pct(aMs)}%` }}
            />
          )}
          {aMs !== null && <Marker label="A" left={pct(aMs)} />}
          {bMs !== null && <Marker label="B" left={pct(bMs)} />}
        </div>
        <span className="font-mono text-xs text-ink-3">{mmss(total)}</span>
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 text-xs font-medium",
            saveState === "saved" ? "text-ok" : "text-warn",
          )}
        >
          <span className={clsx("size-2 rounded-full", saveState === "saved" ? "bg-ok" : "bg-warn")} />
          {saveState === "saved" ? "Đã lưu" : saveState === "offline" ? "Chưa lưu — sẽ đồng bộ lại" : "Đang lưu…"}
        </span>
      </div>
    </div>
  );
}

function Marker({ label, left }: { label: string; left: number }) {
  return (
    <div aria-hidden className="absolute top-0 h-[22px] w-0.5 bg-accent-ink" style={{ left: `${left}%` }}>
      <span className="absolute -top-4 -left-1 font-mono text-[10px] font-semibold text-accent-ink">{label}</span>
    </div>
  );
}
