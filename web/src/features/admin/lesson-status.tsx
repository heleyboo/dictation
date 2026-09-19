import clsx from "clsx";

const STATUS: Record<string, { label: string; className: string }> = {
  processing: { label: "Đang xử lý", className: "bg-pend-soft text-pend" },
  review: { label: "Chờ duyệt", className: "bg-warn-soft text-warn" },
  published: { label: "Đã đăng", className: "bg-ok-soft text-ok" },
  unpublished: { label: "Đã bỏ đăng", className: "bg-surface-2 text-ink-2" },
  failed: { label: "Lỗi", className: "bg-bad-soft text-bad" },
};

export function LessonStatusChip({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, className: "bg-surface-2 text-ink-2" };
  return (
    <span className={clsx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", s.className)}>
      {s.label}
    </span>
  );
}
