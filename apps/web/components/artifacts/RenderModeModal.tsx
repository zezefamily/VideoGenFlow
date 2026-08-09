"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { StoryboardArtifact } from "@/lib/types";

export function RenderModeModal({open,onClose,convId,storyboard,onStarted}:{open:boolean;onClose:()=>void;convId:string;storyboard:StoryboardArtifact;onStarted:()=>void}) {
  const [mode,setMode]=useState<"image"|"video">("image");
  const [strategy,setStrategy]=useState<"smart"|"all"|"custom">("smart");
  const [selected,setSelected]=useState<number[]>([]); const [plan,setPlan]=useState<{selected_shots:number[];estimated_cost:number}|null>(null); const [busy,setBusy]=useState(false);
  useEffect(()=>{if(!open)return; const indices=strategy==="custom"?selected:[]; api.planShotVideos(convId,strategy,indices).then(setPlan).catch(()=>setPlan(null));},[open,strategy,selected,convId]);
  if(!open)return null;
  const start=async()=>{setBusy(true);try{if(mode==="image")await api.renderVideo(convId,"image");else await api.generateShotVideos(convId,strategy,strategy==="custom"?selected:[]);onStarted();onClose();}finally{setBusy(false)}};
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/40 p-4" onClick={onClose}><section className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl" onClick={e=>e.stopPropagation()}>
    <h2 className="text-lg font-semibold">选择成片方式</h2><p className="mt-1 text-xs text-slate-500">视频生成会产生额外费用，提交前请确认预计金额。</p>
    <div className="mt-4 grid grid-cols-2 gap-3">{([['image','图片成片','当前图片动态合成，无额外生成费用'],['video','视频成片','Seedance 2.0 mini · 480p · 无声']] as const).map(x=><button key={x[0]} onClick={()=>setMode(x[0])} className={`rounded-xl border p-3 text-left ${mode===x[0]?'border-indigo-500 bg-indigo-50':'border-slate-200'}`}><b className="text-sm">{x[1]}</b><span className="mt-1 block text-xs text-slate-500">{x[2]}</span></button>)}</div>
    {mode==="video"&&<><div className="mt-4 grid grid-cols-3 gap-2">{([['smart','智能生成'],['all','全部生成'],['custom','自定义']] as const).map(x=><button key={x[0]} onClick={()=>setStrategy(x[0])} className={`rounded-lg border px-3 py-2 text-xs ${strategy===x[0]?'border-indigo-500 bg-indigo-50 text-indigo-700':'border-slate-200'}`}>{x[1]}</button>)}</div>
    {strategy==="custom"&&<div className="mt-3 grid grid-cols-4 gap-2">{storyboard.shots.map(sh=><label key={sh.index} className="flex items-center gap-1 rounded border p-2 text-xs"><input type="checkbox" checked={selected.includes(sh.index)} onChange={()=>setSelected(v=>v.includes(sh.index)?v.filter(i=>i!==sh.index):[...v,sh.index])}/>镜{sh.index}</label>)}</div>}
    <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><b>预计生成 {plan?.selected_shots.length||0} 段视频，约 ¥{(plan?.estimated_cost||0).toFixed(2)}</b><p className="mt-1 text-xs">首镜、尾镜在智能模式下必选；生成失败的镜头合成时自动回退为图片。</p></div></>}
    <div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">取消</button><button disabled={busy||(mode==="video"&&(!plan?.selected_shots.length))} onClick={start} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-40">{busy?'正在提交…':mode==='image'?'确认生成图片成片':`确认付费生成 · ¥${(plan?.estimated_cost||0).toFixed(2)}`}</button></div>
  </section></div>
}
