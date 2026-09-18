import { useEffect } from "react";

export interface DictationShortcutHandlers {
  replaySentence: () => void; // Ctrl+Enter
  togglePlay: () => void; // Ctrl+'
  nextSentence: () => void; // Ctrl+.
  prevSentence: () => void; // Ctrl+,
  hint: () => void; // Ctrl+/
}

/**
 * Một handler duy nhất ở cấp workspace (capture phase).
 * Bỏ qua khi IME tiếng Việt đang composition (Telex/VNI) — xem Risk phase 3.
 */
export function useDictationShortcuts(handlers: DictationShortcutHandlers, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.isComposing) return;
      if (!event.ctrlKey && !event.metaKey) return;
      const map: Record<string, (() => void) | undefined> = {
        Enter: handlers.replaySentence,
        "'": handlers.togglePlay,
        ".": handlers.nextSentence,
        ",": handlers.prevSentence,
        "/": handlers.hint,
      };
      const action = map[event.key];
      if (!action) return;
      event.preventDefault();
      event.stopPropagation();
      action();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [enabled, handlers]);
}

export const SHORTCUT_HELP: { action: string; keys: string }[] = [
  { action: "Phát lại câu", keys: "Ctrl+Enter" },
  { action: "Phát / tạm dừng", keys: "Ctrl+'" },
  { action: "Câu sau", keys: "Ctrl+." },
  { action: "Câu trước", keys: "Ctrl+," },
  { action: "Gợi ý từ tiếp theo", keys: "Ctrl+/" },
  { action: "Sang câu sau khi đúng 100%", keys: "Enter" },
];
