"use client";

import type { StyleOption } from "@/lib/types";

export function StylePickerModal({
  styles,
  onPick,
  onClose,
}: {
  styles: StyleOption[];
  onPick: (name: string) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-[90%] max-w-md overflow-y-auto rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-800">选择画面风格</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>
        <ul className="divide-y divide-gray-100">
          {styles.map((s) => (
            <li key={s.name}>
              <button
                onClick={() => onPick(s.name)}
                className="w-full px-4 py-3 text-left hover:bg-indigo-50"
              >
                <p className="text-sm font-medium text-gray-800">{s.name}</p>
                {s.description && (
                  <p className="mt-0.5 text-xs leading-5 text-gray-500">
                    {s.description}
                  </p>
                )}
              </button>
            </li>
          ))}
          {styles.length === 0 && (
            <li className="px-4 py-6 text-center text-xs text-gray-400">
              画风列表加载中…
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
