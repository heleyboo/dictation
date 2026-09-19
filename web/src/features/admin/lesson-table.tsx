import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api/client";
import { formatDuration } from "@/lib/format";
import { ADMIN_LESSONS_KEY, LEVELS, TOPICS } from "./lesson-options";
import { LessonStatusChip } from "./lesson-status";

const label = (list: readonly { value: string; label: string }[], value: string) =>
  list.find((x) => x.value === value)?.label ?? value;

/** Admin lesson list; refreshes every 5 s while any lesson is processing (AC-M2-02.1). */
export function AdminLessonsPage() {
  const qc = useQueryClient();
  const lessons = useQuery({
    queryKey: ADMIN_LESSONS_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/lessons");
      if (error || !data) throw new Error(errorMessage(error));
      return data;
    },
    refetchInterval: (q) => (q.state.data?.some((l) => l.status === "processing") ? 5000 : false),
  });
  const retry = useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.POST("/api/v1/admin/lessons/{lesson_id}/retry", {
        params: { path: { lesson_id: id } },
      });
      if (error) throw new Error(errorMessage(error));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ADMIN_LESSONS_KEY }),
  });

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-serif text-3xl text-ink">Bài học</h1>
        <Button asChild>
          <Link to="/admin/lessons/new">Thêm bài</Link>
        </Button>
      </div>
      {lessons.isError && <p className="text-bad">{lessons.error.message}</p>}
      {retry.isError && <p className="mb-3 text-sm text-bad">{retry.error.message}</p>}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tiêu đề</TableHead>
            <TableHead>Chủ đề · Trình độ</TableHead>
            <TableHead>Thời lượng</TableHead>
            <TableHead>Câu</TableHead>
            <TableHead>Trạng thái</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {lessons.data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="py-8 text-center text-ink-3">
                Chưa có bài nào.
              </TableCell>
            </TableRow>
          )}
          {lessons.data?.map((l) => (
            <TableRow key={l.id} className={l.status === "failed" ? "bg-bad-soft/60" : undefined}>
              <TableCell className="max-w-md">
                <Link to={`/admin/lessons/${l.id}`} className="font-medium text-ink hover:underline">
                  {l.title}
                </Link>
                {l.status === "failed" && l.error_message && (
                  <pre className="mt-1 max-h-20 overflow-auto font-mono text-xs whitespace-pre-wrap text-bad">
                    {l.error_message}
                  </pre>
                )}
              </TableCell>
              <TableCell className="text-ink-2">
                {label(TOPICS, l.topic)} · {label(LEVELS, l.level)}
              </TableCell>
              <TableCell className="font-mono text-sm">{formatDuration(l.duration_ms)}</TableCell>
              <TableCell className="font-mono text-sm">
                {l.segment_count}
                {l.attention_count > 0 && <span className="ml-1 text-warn">({l.attention_count} cần xem)</span>}
              </TableCell>
              <TableCell>
                <LessonStatusChip status={l.status} />
              </TableCell>
              <TableCell className="text-right">
                {l.status === "failed" && (
                  <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate(l.id)}>
                    Chạy lại
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
