"use client";

export function NextStepCard({
  title,
  primary,
  secondary,
  onPrimary,
  onSecondary,
}: {
  title: string;
  primary: string;
  secondary: string;
  onPrimary: () => void;
  onSecondary: () => void;
}) {
  return (
    <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/45 p-3" aria-label="下一步建议">
      <p className="text-sm font-medium text-slate-800">{title}</p>
      <p className="mt-0.5 text-xs text-slate-500">每一步都由你确认后继续执行。</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button onClick={onPrimary} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          {primary}
        </button>
        <button onClick={onSecondary} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          {secondary}
        </button>
      </div>
    </div>
  );
}
