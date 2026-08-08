"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { StoryboardImage } from "@/lib/types";
import { ImageLightbox } from "./ImageLightbox";

const STATUS_META: Record<
  StoryboardImage["status"],
  { label: string; cls: string; icon: string }
> = {
  pending: { label: "排队中", cls: "bg-gray-100 text-gray-500", icon: "⏳" },
  generating: { label: "生成中", cls: "bg-blue-100 text-blue-600", icon: "🎨" },
  done: { label: "完成", cls: "bg-green-100 text-green-700", icon: "✅" },
  error: { label: "失败", cls: "bg-red-100 text-red-600", icon: "⚠️" },
  cancelled: { label: "已取消", cls: "bg-gray-100 text-gray-400", icon: "✕" },
};

function ImageTile({
  img,
  busy,
  onRegen,
  onPreview,
}: {
  img: StoryboardImage;
  busy: boolean;
  onRegen: () => void;
  onPreview: () => void;
}) {
  const meta = STATUS_META[img.status];
  const done = img.status === "done" && !!img.local_path;
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div
        className={`relative aspect-[9/16] bg-gray-50 ${
          done ? "cursor-zoom-in" : ""
        }`}
        onClick={done ? onPreview : undefined}
      >
        {img.status === "done" && img.local_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.imageUrl(img.local_path)}
            alt={`镜${img.shot_index}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1 text-gray-400">
            <span className="text-2xl">{meta.icon}</span>
            <span className="text-xs">{meta.label}</span>
            {img.status === "generating" && (
              <span className="ml-0.5 inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
            )}
          </div>
        )}
        <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white">
          镜{img.shot_index}
        </span>
        {img.method && (
          <span className="absolute right-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[9px] text-white">
            {img.method === "text2image" ? "文生图" : "图生图"}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between px-2 py-1">
        <span className={`rounded px-1.5 py-0.5 text-[10px] ${meta.cls}`}>
          {meta.label}
        </span>
        {(img.status === "error" || img.status === "done") && (
          <button
            disabled={busy}
            onClick={onRegen}
            className="text-[10px] text-indigo-600 hover:underline disabled:opacity-40"
          >
            {busy ? "重绘中…" : "重绘"}
          </button>
        )}
      </div>
      {img.status === "error" && img.error && (
        <p className="px-2 pb-1 text-[9px] leading-tight text-red-400">
          {img.error.slice(0, 60)}
        </p>
      )}
    </div>
  );
}

/**
 * 图片画廊:展示分镜图生成进度,支持轮询、单张重绘、取消(Phase 4)。
 */
export function ImageGallery({
  convId,
  streamingImages,
}: {
  convId: string;
  streamingImages?: StoryboardImage[] | null;
}) {
  const qc = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);

  const { data } = useQuery({
    queryKey: ["images", convId],
    queryFn: () => api.getImages(convId),
    refetchInterval: (q) =>
      q.state.data?.has_active ? 3000 : false, // 有进行中时 3s 轮询
    refetchOnWindowFocus: false,
  });

  const images = data?.images ?? streamingImages ?? [];
  const hasActive = data?.has_active ?? false;
  const done = images.filter((i) => i.status === "done").length;
  const previewImages = images.filter(
    (image) => image.status === "done" && !!image.local_path
  );

  const handleRegen = async (id: string) => {
    setBusyId(id);
    try {
      await api.regenerateImage(id);
      await qc.invalidateQueries({ queryKey: ["images", convId] });
    } catch (e) {
      alert("重绘失败:" + (e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await api.cancelImages(convId);
      await qc.invalidateQueries({ queryKey: ["images", convId] });
    } finally {
      setCancelling(false);
    }
  };

  if (images.length === 0) return null;

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">🖼️ 分镜图</span>
          <span className="text-xs text-gray-500">
            {done}/{images.length} 完成
          </span>
          {hasActive && (
            <span className="flex items-center gap-1 text-xs text-blue-600">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
              出图中
            </span>
          )}
        </div>
        {hasActive && (
          <button
            disabled={cancelling}
            onClick={handleCancel}
            className="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40"
          >
            {cancelling ? "取消中…" : "取消生成"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3 md:grid-cols-4">
        {images.map((img) => (
          <ImageTile
            key={img.id}
            img={img}
            busy={busyId === img.id}
            onRegen={() => handleRegen(img.id)}
            onPreview={() => setPreviewIndex(previewImages.findIndex((item) => item.id === img.id))}
          />
        ))}
      </div>

      {previewIndex !== null && previewImages[previewIndex] && (
        <ImageLightbox
          images={previewImages}
          currentIndex={previewIndex}
          onChangeIndex={setPreviewIndex}
          onClose={() => setPreviewIndex(null)}
        />
      )}
    </div>
  );
}
