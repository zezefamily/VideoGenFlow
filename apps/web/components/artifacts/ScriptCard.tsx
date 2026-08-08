"use client";

import { useState } from "react";
import type { ScriptArtifact } from "@/lib/types";
import { VersionSelector } from "./VersionSelector";

export function ScriptCard({
  artifact,
  onEdit,
  convId,
  showVersionSelector = false,
}: {
  artifact: ScriptArtifact;
  onEdit?: () => void;
  /** 行为统一由底部 Agent 确认卡承接，保留兼容旧消息渲染调用。 */
  onGenerateStoryboard?: (aspectRatio: string, style: string) => void;
  convId?: string;
  showVersionSelector?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = artifact.content.slice(0, 240);

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">
            📺 {artifact.title}
          </span>
          <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-700">
            v{artifact.version}
          </span>
        </div>
        <span className="text-xs text-gray-500">约 {artifact.duration_sec} 秒</span>
      </div>

      <div className="px-4 py-3">
        <p className="whitespace-pre-wrap text-sm leading-7 text-gray-800">
          {expanded ? artifact.content : `${preview}${artifact.content.length > preview.length ? "…" : ""}`}
        </p>
        {artifact.content.length > preview.length && (
          <button onClick={() => setExpanded((value) => !value)} className="mt-2 text-xs font-medium text-indigo-600 hover:text-indigo-700">
            {expanded ? "收起文案" : "查看完整文案"}
          </button>
        )}

        {artifact.keywords.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {artifact.keywords.map((k) => (
              <span
                key={k}
                className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
              >
                #{k}
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-600 sm:grid-cols-2">
          {artifact.psychology_theory && (
            <div>
              <span className="font-medium text-gray-700">心理学理论：</span>
              {artifact.psychology_theory}
            </div>
          )}
          {artifact.interaction_guide && (
            <div>
              <span className="font-medium text-gray-700">互动引导：</span>
              {artifact.interaction_guide}
            </div>
          )}
        </div>

        {artifact.golden_sentence && (
          <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            💎 {artifact.golden_sentence}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-gray-100 bg-gray-50 px-4 py-2">
        <button
          onClick={onEdit}
          className="rounded px-2.5 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
        >
          ✏️ 修改
        </button>
        <span className="text-[11px] text-slate-400">下一步由下方 Agent 为你确认</span>
      </div>

      {showVersionSelector && convId && (
        <VersionSelector
          convId={convId}
          kind="script"
          activeVersionId={artifact.id}
        />
      )}
    </div>
  );
}
