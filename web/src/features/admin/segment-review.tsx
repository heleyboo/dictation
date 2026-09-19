import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useState, type ReactElement } from "react";
import { Link, useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, errorMessage, type Schemas } from "@/lib/api/client";
import { formatDuration } from "@/lib/format";
import { ADMIN_LESSONS_KEY } from "./lesson-options";
import { LessonStatusChip } from "./lesson-status";
import { useClipPlayer } from "./use-clip-player";

type Lesson = Schemas["LessonDetail"];
type Segment = Schemas["SegmentOut"];

const lessonKey = (id: number) => ["admin", "lesson", id] as const;
const EDITABLE = new Set(["review", "unpublished", "published"]);
const RESTRUCTURABLE = new Set(["review", "unpublished"]);

/** Throws a readable error for non-2xx responses; returns the updated lesson otherwise. */
function unwrap(result: { data?: Lesson; error?: unknown }): Lesson {
  if (result.error || !result.data) throw new Error(errorMessage(result.error));
  return result.data;
}

export function SegmentReviewPage() {
  const lessonId = Number(useParams().lessonId);
  const qc = useQueryClient();
  const lesson = useQuery({
    queryKey: lessonKey(lessonId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/admin/lessons/{lesson_id}", { params: { path: { lesson_id: lessonId } } })),
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 5000 : false),
  });
  const [actionError, setActionError] = useState<string | null>(null);

  /** Every edit endpoint returns the whole lesson; write it straight into the cache. */
  const run = useMutation({
    mutationFn: (action: () => Promise<Lesson>) => action(),
    onMutate: () => setActionError(null),
    onSuccess: (data) => {
      qc.setQueryData(lessonKey(lessonId), data);
      qc.invalidateQueries({ queryKey: ADMIN_LESSONS_KEY });
    },
    onError: (e) => setActionError(e.message),
  });

  if (lesson.isPending) return <p className="p-8 text-sm text-ink-3">Đang tải…</p>;
  if (lesson.isError) return <p className="p-8 text-bad">{lesson.error.message}</p>;
  const l = lesson.data;
  const path = { path: { lesson_id: l.id } };

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <Link to="/admin" className="text-sm text-ink-3 hover:underline">
        ← Bài học
      </Link>
      <header className="mt-2 mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl text-ink">{l.title}</h1>
          <p className="mt-1 text-sm text-ink-2">
            {l.source_url ? (
              <a href={l.source_url} target="_blank" rel="noreferrer">
                {l.source_name}
              </a>
            ) : (
              l.source_name
            )}{" "}
            — {l.license} · <span className="font-mono">{formatDuration(l.duration_ms)}</span> · {l.segment_count} câu
            {l.attention_count > 0 && <span className="text-warn"> · {l.attention_count} câu cần xem</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <LessonStatusChip status={l.status} />
          {RESTRUCTURABLE.has(l.status) && (
            <Button
              disabled={run.isPending}
              onClick={() =>
                run.mutate(async () =>
                  unwrap(await api.POST("/api/v1/admin/lessons/{lesson_id}/publish", { params: path })),
                )
              }
            >
              Đăng bài
            </Button>
          )}
          {l.status === "published" && (
            <Button
              variant="outline"
              disabled={run.isPending}
              onClick={() =>
                run.mutate(async () =>
                  unwrap(await api.POST("/api/v1/admin/lessons/{lesson_id}/unpublish", { params: path })),
                )
              }
            >
              Bỏ đăng
            </Button>
          )}
          {l.status === "failed" && (
            <Button
              variant="outline"
              disabled={run.isPending}
              onClick={() =>
                run.mutate(async () =>
                  unwrap(await api.POST("/api/v1/admin/lessons/{lesson_id}/retry", { params: path })),
                )
              }
            >
              Chạy lại
            </Button>
          )}
        </div>
      </header>

      {l.status === "processing" && (
        <p className="mb-4 rounded-md bg-pend-soft px-3 py-2 text-sm text-pend" role="status">
          Đang căn thời gian và dịch… trang tự làm mới mỗi 5 giây.
        </p>
      )}
      {l.status === "failed" && l.error_message && (
        <pre className="mb-4 max-h-40 overflow-auto rounded-md bg-bad-soft px-3 py-2 font-mono text-xs whitespace-pre-wrap text-bad">
          {l.error_message}
        </pre>
      )}
      {actionError && (
        <p role="alert" className="mb-4 rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
          {actionError}
        </p>
      )}

      {l.segments.length > 0 && (
        <SegmentTable lesson={l} busy={run.isPending} onAction={(action) => run.mutate(action)} />
      )}
    </main>
  );
}

function SegmentTable({
  lesson,
  busy,
  onAction,
}: {
  lesson: Lesson;
  busy: boolean;
  onAction: (action: () => Promise<Lesson>) => void;
}) {
  const { audioRef, playingId, play, stop } = useClipPlayer();
  const editable = EDITABLE.has(lesson.status);
  const restructurable = RESTRUCTURABLE.has(lesson.status);

  return (
    <>
      <audio ref={audioRef} src={lesson.audio_url} preload="metadata" className="hidden" />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">#</TableHead>
            <TableHead className="w-12" />
            <TableHead>English</TableHead>
            <TableHead>Bản dịch</TableHead>
            <TableHead className="w-28">start (ms)</TableHead>
            <TableHead className="w-28">end (ms)</TableHead>
            <TableHead className="w-44" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {lesson.segments.map((s, i) => (
            <SegmentRow
              key={`${s.id}-${s.idx}-${s.text}-${s.start_ms}-${s.end_ms}`}
              segment={s}
              next={lesson.segments[i + 1]}
              editable={editable}
              restructurable={restructurable}
              busy={busy}
              playing={playingId === s.id}
              onPlay={() => (playingId === s.id ? stop() : play(s.id, s.start_ms, s.end_ms))}
              onAction={onAction}
            />
          ))}
        </TableBody>
      </Table>
    </>
  );
}

function SegmentRow({
  segment: s,
  next,
  editable,
  restructurable,
  busy,
  playing,
  onPlay,
  onAction,
}: {
  segment: Segment;
  next: Segment | undefined;
  editable: boolean;
  restructurable: boolean;
  busy: boolean;
  playing: boolean;
  onPlay: () => void;
  onAction: (action: () => Promise<Lesson>) => void;
}) {
  const [text, setText] = useState(s.text);
  const [vi, setVi] = useState(s.translation_vi);
  const [start, setStart] = useState(String(s.start_ms));
  const [end, setEnd] = useState(String(s.end_ms));
  const [splitAt, setSplitAt] = useState("");
  const [splitMs, setSplitMs] = useState("");
  const dirty = text !== s.text || vi !== s.translation_vi || Number(start) !== s.start_ms || Number(end) !== s.end_ms;
  const words = s.text.split(/\s+/);

  const save = () =>
    onAction(async () =>
      unwrap(
        await api.PATCH("/api/v1/admin/segments/{segment_id}", {
          params: { path: { segment_id: s.id } },
          body: { text, translation_vi: vi, start_ms: Number(start), end_ms: Number(end) },
        }),
      ),
    );
  const merge = () =>
    next &&
    onAction(async () =>
      unwrap(await api.POST("/api/v1/admin/segments/merge", { body: { first_id: s.id, second_id: next.id } })),
    );
  const split = () =>
    onAction(async () =>
      unwrap(
        await api.POST("/api/v1/admin/segments/{segment_id}/split", {
          params: { path: { segment_id: s.id } },
          body: { word_index: Number(splitAt), split_ms: s.word_count_aligned ? null : Number(splitMs) },
        }),
      ),
    );

  const lockedHint = "Phải bỏ đăng bài trước khi gộp/tách câu";

  return (
    <TableRow className={clsx(s.needs_attention && "bg-warn-soft/70")}>
      <TableCell className="align-top font-mono text-xs text-ink-3">{s.idx + 1}</TableCell>
      <TableCell className="align-top">
        <Button size="icon" variant="outline" aria-label={playing ? "Dừng" : `Phát câu ${s.idx + 1}`} onClick={onPlay}>
          {playing ? "❚❚" : "▶"}
        </Button>
      </TableCell>
      <TableCell className="align-top">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={!editable}
          rows={2}
          className="min-w-64 font-serif"
          aria-label={`Câu ${s.idx + 1} tiếng Anh`}
        />
        {s.needs_attention && <p className="mt-1 text-xs text-warn">⚠ {s.attention_reason}</p>}
      </TableCell>
      <TableCell className="align-top">
        <Textarea
          value={vi}
          onChange={(e) => setVi(e.target.value)}
          disabled={!editable}
          rows={2}
          className="min-w-64"
          aria-label={`Câu ${s.idx + 1} bản dịch`}
        />
      </TableCell>
      <TableCell className="align-top">
        <Input
          type="number"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          disabled={!editable}
          aria-label="start ms"
        />
      </TableCell>
      <TableCell className="align-top">
        <Input
          type="number"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          disabled={!editable}
          aria-label="end ms"
        />
      </TableCell>
      <TableCell className="align-top">
        <div className="flex flex-col gap-2">
          {dirty && (
            <Button size="sm" disabled={busy} onClick={save}>
              Lưu
            </Button>
          )}
          <Locked locked={!restructurable} hint={lockedHint}>
            <Button size="sm" variant="outline" disabled={!restructurable || busy || !next} onClick={merge}>
              Gộp với câu sau
            </Button>
          </Locked>
          <Locked locked={!restructurable} hint={lockedHint}>
            <div className="flex gap-1">
              <select
                value={splitAt}
                onChange={(e) => setSplitAt(e.target.value)}
                disabled={!restructurable || words.length < 2}
                aria-label="Tách trước từ"
                className="h-8 min-w-0 flex-1 rounded-md border border-input bg-transparent px-1 text-xs"
              >
                <option value="">Tách trước…</option>
                {words.slice(1).map((w, i) => (
                  <option key={i + 1} value={i + 1}>
                    {w}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                variant="outline"
                disabled={!restructurable || busy || !splitAt || (!s.word_count_aligned && !splitMs)}
                onClick={split}
              >
                Tách
              </Button>
            </div>
          </Locked>
          {!s.word_count_aligned && restructurable && splitAt && (
            <Input
              type="number"
              placeholder="split ms"
              value={splitMs}
              onChange={(e) => setSplitMs(e.target.value)}
              aria-label="Mốc tách (ms)"
            />
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

/** Wrap a disabled control with a tooltip explaining why (disabled elements swallow hover events). */
function Locked({ locked, hint, children }: { locked: boolean; hint: string; children: ReactElement }) {
  if (!locked) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0}>{children}</span>
      </TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  );
}
