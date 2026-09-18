import { useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { DiffView } from "./diff-view";
import { applyHint, diffWords } from "./diff/diff-words";
import { scoreTokens } from "./diff/score";
import { splitWords } from "./diff/tokenize";

interface SegmentInputProps {
  index: number;
  /** Câu tiếng Anh — chỉ dùng để so khớp, không bao giờ render nguyên văn khi chưa reveal. */
  expectedText: string;
  translation: string;
  draft: string;
  strict: boolean;
  revealed: boolean;
  hintsUsed: number;
  onDraftChange: (value: string) => void;
  onStrictChange: (value: boolean) => void;
  onReveal: () => void;
  onHint: () => void;
  onComplete: () => void;
  onReplay: () => void;
}

/** Ô nhập của câu đang học + diff + các nút trợ giúp. Chỉ câu hiện tại dùng component này. */
export function SegmentInput({
  index,
  expectedText,
  translation,
  draft,
  strict,
  revealed,
  hintsUsed,
  onDraftChange,
  onStrictChange,
  onReveal,
  onHint,
  onComplete,
  onReplay,
}: SegmentInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [showTranslation, setShowTranslation] = useState(false);

  const expected = useMemo(() => splitWords(expectedText), [expectedText]);
  const tokens = useMemo(() => diffWords(expected, draft, { strict, revealed }), [expected, draft, strict, revealed]);
  const score = useMemo(() => scoreTokens(tokens, expected.length), [tokens, expected.length]);

  const hint = () => {
    const next = applyHint(expected, draft, { strict });
    if (next === null) return;
    onDraftChange(next);
    onHint();
    inputRef.current?.focus();
  };

  return (
    <div className="relative flex gap-3.5 rounded-xl border-[1.5px] border-accent bg-raise p-4 shadow-[0_0_0_4px_var(--accent-soft)]">
      <span className="w-6 shrink-0 font-mono text-[13px] font-semibold leading-[1.9] text-accent-ink">{index}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onKeyDown={(e) => {
            // Ctrl+* do useDictationShortcuts xử lý ở cấp workspace
            if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.nativeEvent.isComposing && score.isPerfect) {
              e.preventDefault();
              onComplete();
            }
          }}
          placeholder="Gõ những gì bạn nghe được…"
          spellCheck={false}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          aria-label={`Câu ${index} — gõ lại nội dung bạn nghe được`}
          disabled={revealed}
          className="w-full rounded-[9px] border border-line-2 bg-surface px-3 py-2.5 font-serif text-[21px] leading-normal text-ink outline-none focus:border-accent disabled:opacity-60"
        />

        <DiffView tokens={tokens} percent={score.percent} />

        {score.isPerfect && (
          <p className="inline-flex w-fit items-center gap-1.5 rounded-full bg-ok-soft px-2.5 py-1 text-xs font-semibold text-ok">
            ✓ Đúng hết — Enter để sang câu sau
          </p>
        )}

        {revealed && (
          <div className="flex items-start gap-2.5 rounded-[10px] border border-warn bg-warn-soft px-3.5 py-3">
            <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-warn">Đã hiện đáp án</span>
            <span className="font-serif text-[19px] leading-snug text-ink">{expectedText}</span>
          </div>
        )}

        {showTranslation && (
          <div className="flex flex-col gap-1 rounded-r-[10px] border-l-[3px] border-accent bg-accent-soft px-3.5 py-3">
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent-ink">Bản dịch</span>
            <span className="text-[15px] leading-relaxed text-ink">{translation}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2.5">
          <Button variant="outline" size="sm" onClick={hint}>
            Gợi ý <kbd className="ml-1.5 font-mono text-[11px] text-ink-3">Ctrl+/</kbd>
          </Button>
          <Button variant="outline" size="sm" onClick={onReveal} disabled={revealed}>
            Hiện đáp án
          </Button>
          <Button
            variant="outline"
            size="sm"
            aria-pressed={showTranslation}
            className={clsx(showTranslation && "border-accent bg-accent-soft text-accent-ink")}
            onClick={() => setShowTranslation((v) => !v)}
          >
            Xem bản dịch
          </Button>
          <Button variant="ghost" size="sm" onClick={onReplay}>
            ↻ Phát lại câu
          </Button>
          <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
            Bắt lỗi dấu câu
            <Switch checked={strict} onCheckedChange={onStrictChange} aria-label="Bắt lỗi dấu câu" />
          </label>
          <span className="text-xs text-ink-3">{hintsUsed ? `${hintsUsed} gợi ý đã dùng` : "Chưa dùng gợi ý"}</span>
        </div>
      </div>
    </div>
  );
}
