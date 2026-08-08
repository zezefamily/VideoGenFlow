"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";

const STAGE_LABEL: Record<string, string> = {
  align: "对齐中",
  ffmpeg: "合成中",
};

/**
 * 成片面板(成片管线第三环):配音完成后,静态分镜 + 音频 + 字幕 -> mp4。
 * 镜像 AudioCard:react-query 轮询 has_active -> 状态机 -> 完成/失败/重生成/取消。
 * 复用 ["audio-track", convId] 缓存判断配音是否就绪(合成依赖音频 + 字幕时间轴)。
 */
export function VideoCard({ convId }: { convId: string }) {
  const qc = useQueryClient();
  const [acting, setActing] = useState(false);

  // 复用 AudioCard 的音轨查询缓存,判断配音是否就绪
  const { data: audio } = useQuery({
    queryKey: ["audio-track", convId],
    queryFn: () => api.getAudioTrack(convId),
    refetchOnWindowFocus: false,
  });
  const hasAudio = audio?.status === "done" && !!audio.audio_url;

  const { data: render } = useQuery({
    queryKey: ["video-render", convId],
    queryFn: () => api.getVideo(convId),
    refetchInterval: (q) => (q.state.data?.has_active ? 3000 : false),
    refetchOnWindowFocus: false,
  });

  // 配音未完成 -> 不渲染(合成依赖音频 + 字幕时间轴)
  if (!hasAudio) return null;

  const status = render?.status;
  const isBusy = status === "pending" || status === "generating";

  const handleRender = async () => {
    setActing(true);
    try {
      await api.renderVideo(convId);
      await qc.invalidateQueries({ queryKey: ["video-render", convId] });
    } catch (e) {
      alert("合成视频失败:" + (e as Error).message);
    } finally {
      setActing(false);
    }
  };

  const handleCancel = async () => {
    setActing(true);
    try {
      await api.cancelVideo(convId);
      await qc.invalidateQueries({ queryKey: ["video-render", convId] });
    } finally {
      setActing(false);
    }
  };

  const handleRegen = async () => {
    if (!render) return;
    setActing(true);
    try {
      await api.regenerateVideo(render.id);
      await qc.invalidateQueries({ queryKey: ["video-render", convId] });
    } catch (e) {
      alert("重新合成失败:" + (e as Error).message);
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="border-b border-gray-200 bg-white px-4 py-2">
      <div className="mx-auto flex max-w-3xl items-center gap-3">
        <span className="text-sm font-semibold text-gray-800">🎬 成片</span>
        {render && <StatusBadge status={status!} stage={render.stage} />}
        <div className="flex-1" />
        {!render && (
          <button
            disabled={acting}
            onClick={handleRender}
            className="rounded-md bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-700 disabled:opacity-40"
          >
            {acting ? "提交中…" : "合成视频"}
          </button>
        )}
        {isBusy && (
          <button
            disabled={acting}
            onClick={handleCancel}
            className="rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40"
          >
            {acting ? "取消中…" : "取消"}
          </button>
        )}
        {render && (status === "done" || status === "error") && (
          <button
            disabled={acting}
            onClick={handleRegen}
            className="rounded-md px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 disabled:opacity-40"
          >
            {acting ? "重新合成中…" : "重新合成"}
          </button>
        )}
      </div>

      {/* 完成:视频播放器 */}
      {render && status === "done" && render.video_url && (
        <div className="mx-auto mt-2 max-w-3xl">
          <video
            src={api.videoUrl(render.video_url)}
            controls
            className="w-full rounded"
          />
          {render.duration_sec != null && (
            <p className="mt-1 text-[10px] text-gray-400">
              时长 {render.duration_sec.toFixed(1)}s · {render.aspect_ratio}
            </p>
          )}
        </div>
      )}

      {/* 失败 */}
      {render && status === "error" && render.error && (
        <p className="mx-auto mt-1 max-w-3xl text-xs text-red-500">
          ⚠️ {render.error}
        </p>
      )}
    </div>
  );
}

function StatusBadge({
  status,
  stage,
}: {
  status: string;
  stage: string | null;
}) {
  if (status === "pending")
    return <span className="text-xs text-gray-500">排队中…</span>;
  if (status === "generating")
    return (
      <span className="flex items-center gap-1 text-xs text-blue-600">
        <span className="inline-block h-2 w-2 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
        {STAGE_LABEL[stage || ""] || "合成中"}
      </span>
    );
  if (status === "done")
    return <span className="text-xs text-green-600">✅ 完成</span>;
  if (status === "error")
    return <span className="text-xs text-red-500">⚠️ 失败</span>;
  if (status === "cancelled")
    return <span className="text-xs text-gray-400">已取消</span>;
  return null;
}
