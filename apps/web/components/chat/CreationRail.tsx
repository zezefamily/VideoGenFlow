"use client";

export type CreationStage = "script" | "storyboard" | "images" | "audio" | "video";

const steps: { id: CreationStage; label: string }[] = [
  { id: "script", label: "脚本" },
  { id: "storyboard", label: "分镜" },
  { id: "images", label: "出图" },
  { id: "audio", label: "配音" },
  { id: "video", label: "成片" },
];

export function CreationRail({
  stage,
  runningLabel,
}: {
  stage: CreationStage | null;
  runningLabel?: string | null;
}) {
  const active = stage ? steps.findIndex((s) => s.id === stage) : -1;
  return (
    <section className="border-b border-slate-100 bg-white px-5 py-2" aria-label="创作进度">
      <div className="mx-auto flex max-w-3xl items-center gap-2 overflow-x-auto">
        <span className="mr-1 text-[11px] font-medium text-slate-400">当前进度</span>
        {steps.map((step, index) => {
          const done = index < active;
          const current = index === active;
          return (
            <div className="flex items-center gap-2" key={step.id}>
              <span className={
                "inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs transition-colors " +
                (current ? "bg-indigo-600 text-white" : done ? "bg-emerald-50 text-emerald-700" : "bg-slate-50 text-slate-400")
              }>
                {done ? "✓" : current && runningLabel ? "◌" : "○"} {step.label}
              </span>
              {index < steps.length - 1 && <span className="h-px w-3 bg-slate-200" />}
            </div>
          );
        })}
        {runningLabel && <span className="ml-auto shrink-0 text-xs text-indigo-600">{runningLabel}</span>}
      </div>
    </section>
  );
}
