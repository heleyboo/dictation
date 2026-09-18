import clsx from "clsx";
import type { Token } from "./diff/diff-words";

const STYLE: Record<Token["status"], { className: string; label: string; icon: string }> = {
  correct: { className: "diff-token diff-correct", label: "Đúng", icon: "✓" },
  wrong: { className: "diff-token diff-wrong", label: "Sai — thử nghe lại", icon: "~" },
  extra: { className: "diff-token diff-extra", label: "Thừa từ", icon: "×" },
  missing: { className: "diff-token diff-missing", label: "Thiếu một từ", icon: "_" },
  pending: { className: "diff-token diff-pending", label: "Đang gõ — khớp tới đây", icon: "·" },
  revealed: { className: "diff-token diff-revealed", label: "Đã hiện đáp án", icon: "!" },
};

interface DiffViewProps {
  tokens: Token[];
  /** Điểm để đọc kèm cho screen reader; null = câu đã hiện đáp án. */
  percent: number | null;
  className?: string;
}

/**
 * Hiển thị diff dưới ô nhập. Không bao giờ render từ đúng của token `missing`/`wrong`
 * — chỉ ô trống hoặc chính chữ người học đã gõ.
 */
export function DiffView({ tokens, percent, className }: DiffViewProps) {
  return (
    <div
      className={clsx(
        "flex min-h-9 flex-wrap items-center gap-x-2 gap-y-1 font-serif text-[1.3125rem] leading-relaxed",
        className,
      )}
      aria-live="polite"
      aria-atomic="true"
    >
      {tokens.map((token, i) => {
        const style = STYLE[token.status];
        return (
          <span
            key={`${i}-${token.status}-${token.text}`}
            className={style.className}
            title={style.label}
            aria-label={`${style.label}${token.text ? `: ${token.text}` : ""}`}
            data-status={token.status}
          >
            {token.status === "missing" ? "＿＿＿" : token.text}
            <span aria-hidden className="ml-1 align-super font-sans text-[0.625rem] opacity-70">
              {style.icon}
            </span>
          </span>
        );
      })}
      <span className="sr-only">{percent === null ? "Câu đã hiện đáp án" : `Điểm hiện tại ${percent}%`}</span>
    </div>
  );
}
