"use client";

import { useEffect, useState } from "react";
import type { StoryboardImage } from "@/lib/types";
import { api } from "@/lib/api";

/** 分镜图大图预览:点击遮罩或 ESC 关闭，支持左右切换与下载原图。 */
export function ImageLightbox({
  images,
  currentIndex,
  onChangeIndex,
  onClose,
}: {
  images: StoryboardImage[];
  currentIndex: number;
  onChangeIndex: (index: number) => void;
  onClose: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const img = images[currentIndex];
  const hasMultiple = images.length > 1;
  const previous = () =>
    onChangeIndex((currentIndex - 1 + images.length) % images.length);
  const next = () => onChangeIndex((currentIndex + 1) % images.length);

  const url = img
    ? img.local_path
      ? api.imageUrl(img.local_path)
      : img.image_url || ""
    : "";

  // ESC 关闭 + 锁背景滚动
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (hasMultiple && e.key === "ArrowLeft") previous();
      if (hasMultiple && e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [currentIndex, hasMultiple, onClose, images.length]);

  if (!img || !url) return null;

  const handleDownload = async () => {
    if (!url) return;
    setDownloading(true);
    try {
      // fetch blob 绕过跨域 <a download> 限制,确保触发下载而非导航
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const ext = img.local_path?.split(".").pop() || "png";
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = `镜${img.shot_index}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objUrl);
    } catch {
      // 失败回退:新标签打开,用户可右键另存
      window.open(url, "_blank");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/85"
      onClick={onClose}
    >
      {/* 顶部工具栏 */}
      <div
        className="flex items-center justify-between px-4 py-3 text-white"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="text-sm font-medium">镜{img.shot_index} <span className="ml-1 text-white/60">{currentIndex + 1}/{images.length}</span></span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="rounded bg-white/15 px-3 py-1 text-xs font-medium text-white hover:bg-white/25 disabled:opacity-50"
          >
            {downloading ? "下载中…" : "⬇ 下载"}
          </button>
          <button
            onClick={onClose}
            className="rounded bg-white/15 px-2.5 py-1 text-xs text-white hover:bg-white/25"
          >
            ✕
          </button>
        </div>
      </div>

      {/* 大图(完整显示,不裁剪) */}
      <div
        className="flex flex-1 items-center justify-center overflow-auto p-4"
        onClick={onClose}
      >
        {hasMultiple && (
          <button
            aria-label="查看上一张分镜图"
            onClick={(e) => { e.stopPropagation(); previous(); }}
            className="absolute left-3 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/45 px-3 py-2 text-2xl text-white transition hover:bg-black/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
          >
            ‹
          </button>
        )}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt={`镜${img.shot_index}大图`}
          onClick={(e) => e.stopPropagation()}
          className="max-h-full max-w-full rounded object-contain"
        />
        {hasMultiple && (
          <button
            aria-label="查看下一张分镜图"
            onClick={(e) => { e.stopPropagation(); next(); }}
            className="absolute right-3 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/45 px-3 py-2 text-2xl text-white transition hover:bg-black/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
          >
            ›
          </button>
        )}
      </div>

      {/* 生成提示词(可选,辅助确认画面) */}
      {img.prompt && (
        <div
          className="max-h-32 overflow-y-auto bg-black/60 px-4 py-2 text-xs leading-5 text-gray-200"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="font-medium text-gray-400">提示词：</span>
          {img.prompt}
        </div>
      )}
    </div>
  );
}
