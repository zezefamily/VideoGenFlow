"use client";

import { useState } from "react";
import type { StyleOption } from "@/lib/types";

/** 分镜画面比例选项。默认 16:9 横屏。 */
const ASPECT_RATIOS = [
  { value: "16:9", label: "16:9 横屏", hint: "B站 / YouTube" },
  { value: "9:16", label: "9:16 竖屏", hint: "抖音 / 视频号 / 小红书" },
  { value: "1:1", label: "1:1 方屏", hint: "朋友圈 / Instagram" },
];

/** 生成分镜前的选择弹窗:选画面比例 + 画风,确认后回调。
 *  默认 16:9 横屏 + 首个画风(黑板粉笔手绘风)。 */
export function StoryboardGenPickerModal({
  styles,
  onConfirm,
  onClose,
}: {
  styles: StyleOption[];
  onConfirm: (aspectRatio: string, style: string) => void;
  onClose: () => void;
}) {
  const [aspect, setAspect] = useState("16:9");
  const [style, setStyle] = useState<string>(styles[0]?.name ?? "");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-[90%] max-w-md overflow-y-auto rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-800">生成分镜</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        {/* 画面比例 */}
        <div className="px-4 py-3">
          <p className="mb-2 text-xs font-medium text-gray-600">画面比例</p>
          <div className="grid grid-cols-3 gap-2">
            {ASPECT_RATIOS.map((r) => (
              <button
                key={r.value}
                onClick={() => setAspect(r.value)}
                className={
                  aspect === r.value
                    ? "rounded-md border-2 border-indigo-500 bg-indigo-50 px-2 py-2 text-center"
                    : "rounded-md border border-gray-200 px-2 py-2 text-center hover:border-indigo-300"
                }
              >
                <p className="text-xs font-semibold text-gray-800">{r.label}</p>
                <p className="mt-0.5 text-[10px] text-gray-400">{r.hint}</p>
              </button>
            ))}
          </div>
        </div>

        {/* 画风 */}
        <div className="border-t border-gray-100 px-4 py-3">
          <p className="mb-2 text-xs font-medium text-gray-600">画面风格</p>
          <ul className="divide-y divide-gray-100">
            {styles.map((s) => (
              <li key={s.name}>
                <button
                  onClick={() => setStyle(s.name)}
                  className={
                    style === s.name
                      ? "w-full px-2 py-2.5 text-left bg-indigo-50"
                      : "w-full px-2 py-2.5 text-left hover:bg-indigo-50"
                  }
                >
                  <p className="text-sm font-medium text-gray-800">
                    {style === s.name ? "✓ " : ""}
                    {s.name}
                  </p>
                  {s.description && (
                    <p className="mt-0.5 text-xs leading-5 text-gray-500">
                      {s.description}
                    </p>
                  )}
                </button>
              </li>
            ))}
            {styles.length === 0 && (
              <li className="px-2 py-6 text-center text-xs text-gray-400">
                画风列表加载中…
              </li>
            )}
          </ul>
        </div>

        {/* 操作 */}
        <div className="flex items-center justify-end gap-2 border-t border-gray-100 bg-gray-50 px-4 py-2">
          <button
            onClick={onClose}
            className="rounded px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100"
          >
            取消
          </button>
          <button
            onClick={() => style && onConfirm(aspect, style)}
            disabled={!style}
            className={
              style
                ? "rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                : "cursor-not-allowed rounded bg-gray-300 px-3 py-1.5 text-xs text-gray-500"
            }
          >
            生成
          </button>
        </div>
      </div>
    </div>
  );
}
