"use client";

export function WelcomePanel({ onChoose }: { onChoose: (text: string) => void }) {
  const choices = [
    ["分析抖音链接", "我想分析这个抖音链接，做一条同类型视频："],
    ["从话题开始", "我想做一条关于"],
    ["粘贴口播文案", "这是我的口播文案，请帮我继续做成视频："],
  ] as const;
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
      <p className="text-base font-semibold tracking-tight text-slate-900">从一个想法，做成一条视频。</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">你给方向，我负责把脚本、分镜、画面、配音和成片串起来。</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {choices.map(([label, text]) => <button key={label} onClick={() => onChoose(text)} className="rounded-xl border border-slate-200 px-3 py-3 text-left text-sm font-medium text-slate-700 hover:border-indigo-200 hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">{label}<span className="mt-1 block text-xs font-normal text-slate-400">填入输入框</span></button>)}
      </div>
    </div>
  );
}
