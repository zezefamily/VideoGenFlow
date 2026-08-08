"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { StoryboardArtifact } from "@/lib/types";
import { api } from "@/lib/api";
import { VersionSelector } from "./VersionSelector";
import { StylePickerModal } from "./StylePickerModal";

const ASPECT_HINT: Record<string, string> = {
  "9:16": "竖屏",
  "16:9": "横屏",
  "1:1": "方屏",
};

export function StoryboardCard({
  artifact,
  onEdit,
  onGenerateImages,
  convId,
  showVersionSelector = false,
}: {
  artifact: StoryboardArtifact;
  onEdit?: () => void;
  onGenerateImages?: (style: string) => void;
  convId?: string;
  showVersionSelector?: boolean;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const { data: styles = [] } = useQuery({
    queryKey: ["styles"],
    queryFn: () => api.getStyles(),
    staleTime: Infinity,
  });

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">
            🎬 分镜表
          </span>
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-700">
            v{artifact.version}
          </span>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
            {ASPECT_HINT[artifact.aspect_ratio] || artifact.aspect_ratio}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {artifact.shot_count} 镜 · 约 {artifact.total_duration_sec} 秒
        </span>
      </div>

      <ol className="divide-y divide-gray-100">
        {artifact.shots.map((sh) => (
          <li key={sh.index} className="px-4 py-3">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                {sh.index}
              </span>
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">
                    {sh.title}
                  </span>
                  {sh.camera && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                      {sh.camera}
                    </span>
                  )}
                  {sh.duration_sec > 0 && (
                    <span className="text-[11px] text-gray-400">
                      {sh.duration_sec}s
                    </span>
                  )}
                </div>
                {sh.visual && (
                  <p className="mt-1 text-xs leading-6 text-gray-600">
                    <span className="font-medium text-gray-500">画面：</span>
                    {sh.visual}
                  </p>
                )}
                {sh.video_prompt && (
                  <p className="mt-1 text-xs leading-6 text-gray-600">
                    <span className="font-medium text-gray-500">视频：</span>
                    {sh.video_prompt}
                  </p>
                )}
                {sh.narration && (
                  <p className="mt-1 text-xs leading-6 text-gray-800">
                    <span className="font-medium text-gray-500">旁白：</span>
                    {sh.narration}
                  </p>
                )}
                {sh.notes && (
                  <p className="mt-1 text-[11px] text-gray-400">📝 {sh.notes}</p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>

      <div className="flex items-center gap-2 border-t border-gray-100 bg-gray-50 px-4 py-2">
        <button
          onClick={onEdit}
          className="rounded px-2.5 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
        >
          ✏️ 修改某镜
        </button>
        <button
          onClick={() => onGenerateImages && setPickerOpen(true)}
          disabled={!onGenerateImages}
          title={onGenerateImages ? "为每个镜头生成分镜图" : "需要激活分镜"}
          className={
            onGenerateImages
              ? "rounded px-2.5 py-1 text-xs font-medium text-emerald-600 hover:bg-emerald-50"
              : "cursor-not-allowed rounded px-2.5 py-1 text-xs text-gray-400"
          }
        >
          🎨 生成图片
        </button>
        <span className="text-[11px] text-gray-400">
          提示：在输入框说"把第3镜改成…"即可单镜修改
        </span>
      </div>

      {pickerOpen && onGenerateImages && (
        <StylePickerModal
          styles={styles}
          onPick={(name) => {
            setPickerOpen(false);
            onGenerateImages(name);
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {showVersionSelector && convId && (
        <VersionSelector
          convId={convId}
          kind="storyboard"
          activeVersionId={artifact.id}
        />
      )}
    </div>
  );
}
