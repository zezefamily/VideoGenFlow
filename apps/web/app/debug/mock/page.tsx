"use client";
import { useState } from "react";

type Line = { role: "user" | "agent"; text: string; card?: string };
const seed: Line[] = [
  { role:"agent", text:"你好，我是你的短视频创作搭档。你可以发链接、话题或口播文案。" },
  { role:"user", text:"我想分析这个抖音链接，做一条同类型视频： https://v.douyin.com/RH0HfIWptz0/" },
  { role:"agent", text:"我已提取原视频文案。它不是在讲“压住情绪”，而是在讲：一次小失控，如何把自己推向更大的损失。" , card:"分析完成 · 核心命题：情绪失控会放大最初的小错误；成熟是及时止损。"},
];
export default function MockChat(){
 const [lines,setLines]=useState(seed); const [step,setStep]=useState(0);
 const next=()=>{const flows=[
  {text:"我会保留原视频的冲突结构：小刺激 → 失控升级 → 现实代价 → 及时止损；只换一个全新的故事。要继续仿写吗？",card:"仿写建议 · 保留主题，不复用原故事"},
  {text:"脚本完成。新故事仍然围绕“别让第一次失控，决定你后面的损失”。你想先修改文案，还是生成分镜？",card:"脚本 · 58 秒 · 3 个可截图金句"},
  {text:"分镜完成。我已让每一镜承担不同视觉功能：规则、诱因、升级、代价、现实映射、转身，避免连续同构画面。",card:"分镜 · 12 镜 · 16:9 · 镜头差异检查通过"},
  {text:"分镜图、黄色黑描边字幕和配音均已完成。现在可以合成成片。",card:"配音 · 44.2 秒 · 28 段字幕"},
  {text:"成片完成。你可以播放检查节奏，或回到任一阶段修改后重新生成。",card:"成片 · 16:9 · 黄色字幕 · H.264 + AAC"},
 ]; const item=flows[step]; if(!item)return; setLines(v=>[...v,{role:"agent",...item}]);setStep(v=>v+1)};
 return <main className="flex h-screen flex-col bg-[#fcfcfc]"><header className="border-b bg-white px-5 py-3 text-sm font-semibold">Mock · 情绪及时止损做同款</header><div className="mx-auto w-full max-w-3xl flex-1 space-y-5 overflow-y-auto px-4 py-6">{lines.map((l,i)=><div key={i} className={l.role==="user"?"ml-auto max-w-[78%] rounded-2xl bg-indigo-600 px-4 py-3 text-sm text-white":"max-w-[86%]"}><p className="whitespace-pre-wrap text-sm leading-6">{l.text}</p>{l.card&&<div className="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-slate-700 shadow-sm">{l.card}</div>}</div>)}</div><div className="border-t bg-white p-4"><div className="mx-auto flex max-w-3xl items-center gap-2"><button onClick={next} disabled={step>=5} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{step>=5?"已完成":"确认，继续下一步"}</button><button className="rounded-lg border px-4 py-2 text-sm">修改当前结果</button><span className="ml-auto text-xs text-slate-400">Mock 对话 · 不调用外部服务</span></div></div></main>
}
