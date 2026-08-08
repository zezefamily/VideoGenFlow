"use client";

import { useEffect, useState } from "react";
import { getTTSProvider, setTTSProvider, type TTSProvider, VOLC_DEFAULT_TTS } from "@/lib/tts-settings";

export function TTSSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [provider, setProviderState] = useState<TTSProvider>("volcengine");

  useEffect(() => {
    if (open) setProviderState(getTTSProvider());
  }, [open]);

  if (!open) return null;

  const save = () => {
    setTTSProvider(provider);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 p-4" onClick={onClose}>
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="tts-settings-title">
        <div className="flex items-center justify-between">
          <div><p className="text-[11px] font-medium tracking-[0.18em] text-indigo-600">VOICE ENGINE</p><h2 id="tts-settings-title" className="mt-1 text-lg font-semibold text-slate-900">配音设置</h2></div>
          <button onClick={onClose} aria-label="关闭设置" className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100">✕</button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2">
          {(["volcengine", "dubbingx"] as TTSProvider[]).map((item) => (
            <button key={item} onClick={() => setProviderState(item)} className={`rounded-xl border p-3 text-left transition ${provider === item ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-100" : "border-slate-200 hover:border-slate-300"}`}>
              <span className="text-sm font-semibold text-slate-900">{item === "volcengine" ? "豆包语音" : "DubbingX"}</span>
              <span className="mt-1 block text-[11px] text-slate-500">{item === "volcengine" ? "火山引擎官方 TTS" : "现有配音服务"}</span>
            </button>
          ))}
        </div>

        {provider === "volcengine" && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs text-slate-500">默认音色</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">爽快思思（多情感）</p>
            <p className="mt-1 break-all font-mono text-[10px] text-indigo-600">{VOLC_DEFAULT_TTS.voiceId}</p>
            <div className="mt-4 grid grid-cols-4 gap-2 text-center">
              {[['情感', VOLC_DEFAULT_TTS.emotionLabel], ['语速', VOLC_DEFAULT_TTS.speedLabel], ['音调', VOLC_DEFAULT_TTS.pitch], ['音量', '默认']].map(([label, value]) => <div key={label as string} className="rounded-lg bg-white px-2 py-2"><p className="text-[10px] text-slate-400">{label}</p><p className="mt-1 text-xs font-medium text-slate-800">{value}</p></div>)}
            </div>
            <p className="mt-3 text-[11px] leading-5 text-slate-400">当前版本使用固定默认音色与参数，自定义参数暂不开放。</p>
          </div>
        )}

        <button onClick={save} className="mt-5 w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">保存设置</button>
      </section>
    </div>
  );
}
