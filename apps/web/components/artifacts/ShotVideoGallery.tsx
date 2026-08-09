"use client";

import { api } from "@/lib/api";
import type { ShotVideoList } from "@/lib/types";

const STATUS = {
  pending: { label: "排队中", cls: "bg-slate-100 text-slate-500", icon: "⏳" },
  generating: { label: "生成中", cls: "bg-blue-100 text-blue-600", icon: "🎬" },
  done: { label: "完成", cls: "bg-green-100 text-green-700", icon: "✅" },
  error: { label: "失败", cls: "bg-red-100 text-red-600", icon: "⚠️" },
} as const;

export function ShotVideoGallery({ data }: { data: ShotVideoList }) {
  if (!data.assets.length) return null;
  const assets = [...data.assets].sort((a, b) => a.shot_index - b.shot_index);
  const done = assets.filter((asset) => asset.status === "done").length;

  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">🎬 分镜视频</span>
          <span className="text-xs text-slate-500">{done}/{assets.length} 完成</span>
          {data.has_active && (
            <span className="flex items-center gap-1 text-xs text-blue-600">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
              生成中
            </span>
          )}
        </div>
        <span className="text-xs text-amber-700">预计 ¥{data.estimated_cost.toFixed(2)}</span>
      </header>

      <div className="grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 md:grid-cols-3">
        {assets.map((asset) => {
          const meta = STATUS[asset.status];
          const playable = asset.status === "done" && !!asset.local_path;
          return (
            <article key={asset.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="relative aspect-video bg-slate-950">
                {playable ? (
                  <video
                    src={api.videoUrl(asset.local_path!)}
                    controls
                    playsInline
                    preload="metadata"
                    className="h-full w-full object-contain"
                    aria-label={`分镜 ${asset.shot_index} 视频`}
                  />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-slate-400">
                    <span className="text-2xl">{meta.icon}</span>
                    <span className="text-xs">{meta.label}</span>
                    {asset.status === "generating" && (
                      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
                    )}
                  </div>
                )}
                <span className="absolute left-1.5 top-1.5 rounded bg-black/65 px-1.5 py-0.5 text-[10px] font-medium text-white">
                  镜{asset.shot_index} · {asset.duration_sec}s
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 px-2 py-1.5">
                <span className={`rounded px-1.5 py-0.5 text-[10px] ${meta.cls}`}>{meta.label}</span>
                <span className="text-[10px] text-slate-400">480p · ¥{asset.estimated_cost.toFixed(2)}</span>
              </div>
              {asset.status === "error" && asset.error && (
                <p className="px-2 pb-2 text-[10px] leading-4 text-red-500">{asset.error.slice(0, 100)}</p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
