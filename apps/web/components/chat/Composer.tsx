"use client";

import { type RefObject } from "react";

export function Composer({
  onSend,
  disabled,
  draft,
  setDraft,
  inputRef,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
  draft: string;
  setDraft: (v: string) => void;
  inputRef?: RefObject<HTMLTextAreaElement>;
}) {
  const submit = () => {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
  };

  return (
    <div className="border-t border-gray-200 bg-white p-3">
      <div className="flex items-end gap-2 rounded-xl border border-gray-300 bg-white px-3 py-2 focus-within:border-indigo-400">
        <textarea
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={1}
          placeholder="发链接、话题或口播文案，和我一起开始创作…"
          className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-gray-400 focus-visible:ring-0"
        />
        <button
          onClick={submit}
          disabled={disabled || !draft.trim()}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          发送
        </button>
      </div>
    </div>
  );
}
