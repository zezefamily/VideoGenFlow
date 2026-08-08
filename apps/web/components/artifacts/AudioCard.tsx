"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AudioTrack, SubtitleSegment } from "@/lib/types";
import { getTTSProvider, VOLC_DEFAULT_TTS } from "@/lib/tts-settings";

const STAGE_LABEL: Record<string, string> = {
  tts: "TTS 合成中",
  ata: "字幕打轴中",
};

function fmtMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

/**
 * 配音面板(成片管线):脚本就绪后出现,一键生成整段配音 + ATA 字幕打轴。
 * 镜像 ImageGallery:react-query 轮询 has_active -> 状态机 -> 完成/失败/重生成/取消。
 * TTS 不走聊天 SSE,是独立 REST 调用,故作为持久面板挂在聊天页(非消息气泡)。
 */
export function AudioCard({
  convId,
  hasScript,
}: {
  convId: string;
  hasScript: boolean;
}) {
  const qc = useQueryClient();
  const [acting, setActing] = useState(false);
  const [activeMs, setActiveMs] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { data: track } = useQuery({
    queryKey: ["audio-track", convId],
    queryFn: () => api.getAudioTrack(convId),
    refetchInterval: (q) => (q.state.data?.has_active ? 3000 : false),
    refetchOnWindowFocus: false,
  });

  // 脚本不存在 -> 不渲染(后端 generate 也要求有激活脚本)
  if (!hasScript) return null;

  const status = track?.status;
  const isBusy = status === "pending" || status === "generating";

  const handleGenerate = async () => {
    setActing(true);
    try {
      const provider = getTTSProvider();
      await api.generateTTS(convId, provider === "volcengine" ? { provider, voice_id: VOLC_DEFAULT_TTS.voiceId, emotion: VOLC_DEFAULT_TTS.emotion, audio_speed: VOLC_DEFAULT_TTS.speed, audio_pitch: VOLC_DEFAULT_TTS.pitch, audio_volume: VOLC_DEFAULT_TTS.volume } : { provider });
      await qc.invalidateQueries({ queryKey: ["audio-track", convId] });
    } catch (e) {
      alert("生成配音失败:" + (e as Error).message);
    } finally {
      setActing(false);
    }
  };

  const handleCancel = async () => {
    setActing(true);
    try {
      await api.cancelTTS(convId);
      await qc.invalidateQueries({ queryKey: ["audio-track", convId] });
    } finally {
      setActing(false);
    }
  };

  const handleRegen = async () => {
    if (!track) return;
    setActing(true);
    setActiveMs(null);
    try {
      await api.regenerateTrack(track.id);
      await qc.invalidateQueries({ queryKey: ["audio-track", convId] });
    } catch (e) {
      alert("重新生成失败:" + (e as Error).message);
    } finally {
      setActing(false);
    }
  };

  const onTimeUpdate = () => {
    const el = audioRef.current;
    if (el) setActiveMs(el.currentTime * 1000);
  };

  return (
    <div className="border-b border-gray-200 bg-white px-4 py-2">
      <div className="mx-auto flex max-w-3xl items-center gap-3">
        <span className="text-sm font-semibold text-gray-800">🎙️ 配音</span>
        {track && <StatusBadge status={status!} stage={track.stage} />}
        <div className="flex-1" />
        {!track && (
          <button
            disabled={acting}
            onClick={handleGenerate}
            className="rounded-md bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-700 disabled:opacity-40"
          >
            {acting ? "提交中…" : "生成配音"}
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
        {track && (status === "done" || status === "error") && (
          <button
            disabled={acting}
            onClick={handleRegen}
            className="rounded-md px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 disabled:opacity-40"
          >
            {acting ? "重新生成中…" : "重新生成"}
          </button>
        )}
      </div>

      {/* 完成:播放器 + 字幕(跟随高亮 + 点击跳转)*/}
      {track && status === "done" && track.audio_url && (
        <div className="mx-auto mt-2 max-w-3xl">
          <audio
            ref={audioRef}
            src={api.audioUrl(track.audio_url)}
            controls
            onTimeUpdate={onTimeUpdate}
            className="w-full"
          />
          {track.audio_duration_sec != null && (
            <p className="mt-1 text-[10px] text-gray-400">
              {track.provider === "volcengine" ? "豆包语音" : "DubbingX"} · 时长 {track.audio_duration_sec.toFixed(1)}s ·{" "}
              {track.subtitles.length} 句字幕
            </p>
          )}
          {track.subtitles.length > 0 && (
            <div className="mt-1 max-h-48 overflow-y-auto rounded border border-gray-100 bg-gray-50 p-1.5">
              {track.subtitles.map((seg, i) => (
                <SubtitleRow
                  key={i}
                  seg={seg}
                  active={
                    activeMs != null &&
                    activeMs >= seg.start_ms &&
                    activeMs < seg.end_ms
                  }
                  onSeek={(ms) => {
                    if (audioRef.current) {
                      audioRef.current.currentTime = ms / 1000;
                      audioRef.current.play();
                    }
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* 失败 */}
      {track && status === "error" && track.error && (
        <p className="mx-auto mt-1 max-w-3xl text-xs text-red-500">
          ⚠️ {track.error}
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
        {STAGE_LABEL[stage || ""] || "生成中"}
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

function SubtitleRow({
  seg,
  active,
  onSeek,
}: {
  seg: SubtitleSegment;
  active: boolean;
  onSeek: (ms: number) => void;
}) {
  return (
    <div
      className={`flex cursor-pointer gap-2 rounded px-1.5 py-1 text-xs hover:bg-white ${
        active ? "bg-indigo-100 text-indigo-700" : "text-gray-700"
      }`}
      onClick={() => onSeek(seg.start_ms)}
    >
      <span className="shrink-0 font-mono text-[10px] text-gray-400">
        {fmtMs(seg.start_ms)}
      </span>
      <span className="leading-snug">{seg.text}</span>
    </div>
  );
}
