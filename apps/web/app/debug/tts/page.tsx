"use client";

import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DebugTTSParams, DebugTTSResult } from "@/lib/types";

const DEFAULT_TEXT =
  "心理学上有一个现象叫做蔡加尼克效应：人们天生更容易记住那些未完成的事情。" +
  "这就是为什么，你总是放不下那段没有结果的感情。";

function fmtMs(ms: number) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

/**
 * TTS 调试台(临时):自由调音色/情绪类型/风格/档位/语速语调音量/autoPause/打轴,
 * 生成试听 + 历史对比,找到效果好的参数后再定默认值。不落库,不依赖会话/脚本。
 */
export default function TTSDebugPage() {
  const [voiceId, setVoiceId] = useState("678415");
  const [emoType, setEmoType] = useState("常规");
  const [aura, setAura] = useState("日常说话");
  const [level, setLevel] = useState(1);
  const [speed, setSpeed] = useState(1.0);
  const [pitch, setPitch] = useState(1.0);
  const [volume, setVolume] = useState(0);
  const [text, setText] = useState(DEFAULT_TEXT);
  const [autoPause, setAutoPause] = useState(false);
  const [align, setAlign] = useState(false);
  const [onlyMine, setOnlyMine] = useState(true);

  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DebugTTSResult | null>(null);
  const [lastParams, setLastParams] = useState<DebugTTSParams | null>(null);
  const [activeMs, setActiveMs] = useState<number | null>(null);
  const [history, setHistory] = useState<{ label: string; result: DebugTTSResult }[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { data: voiceData } = useQuery({
    queryKey: ["tts-debug-voices", onlyMine],
    queryFn: () => api.listVoices(500, onlyMine ? true : undefined),
  });
  const { data: emoData } = useQuery({
    queryKey: ["tts-debug-emotions", voiceId],
    queryFn: () => api.getEmotions(voiceId),
    enabled: !!voiceId,
  });

  const voices = voiceData?.list ?? [];
  const emotions = emoData?.list ?? [];
  const auras = emotions.find((e) => e.type === emoType)?.auras ?? [];
  const emotionString = emoType && aura ? `${emoType}-${aura}-${level}` : null;

  const labelFor = () => {
    const emo = emotionString || "自动";
    return `${emo} | ${speed.toFixed(2)}/${pitch.toFixed(2)}/${volume}${
      autoPause ? " | pause" : ""
    }${align ? " | align" : ""}`;
  };

  const handleAnalyze = async () => {
    if (!text.trim()) return;
    setAnalyzing(true);
    setError(null);
    try {
      const { emotion } = await api.analyzeEmotion(text);
      const parts = emotion.split("-");
      if (parts.length >= 3) {
        setEmoType(parts[0]);
        setAura(parts[1]);
        const lv = parseInt(parts[2], 10);
        if (!Number.isNaN(lv)) setLevel(lv);
      }
    } catch (e) {
      setError("分析情绪失败:" + (e as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    if (!text.trim() || !voiceId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveMs(null);
    const body: DebugTTSParams = {
      text,
      voice_id: voiceId,
      emotion: emotionString,
      language: "zh",
      audio_speed: speed,
      audio_pitch: pitch,
      audio_volume: volume,
      file_format: "mp3",
      auto_pause: autoPause,
      align,
    };
    setLastParams(body);
    try {
      const res = await api.debugSynthesize(body);
      setResult(res);
      setHistory((h) => [{ label: labelFor(), result: res }, ...h].slice(0, 10));
    } catch (e) {
      setError("生成失败:" + (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-6">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-4 text-lg font-bold text-gray-800">
          🎚️ TTS 调试台
          <span className="ml-2 text-xs font-normal text-gray-400">
            临时 · 调参试听对比 · 不落库
          </span>
        </h1>

        {error && (
          <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            ⚠️ {error}
          </div>
        )}

        {/* 参数表单 */}
        <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-gray-600">音色</label>
              <label className="flex items-center gap-1 text-xs text-gray-500">
                <input
                  type="checkbox"
                  checked={onlyMine}
                  onChange={(e) => setOnlyMine(e.target.checked)}
                />
                仅自定义音色
              </label>
            </div>
            <select
              value={voiceId}
              onChange={(e) => {
                setVoiceId(e.target.value);
                setEmoType("");
                setAura("");
              }}
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}({v.id}) · {v.grade} · {v.version}
                </option>
              ))}
            </select>
            {voices.length === 0 && (
              <p className="mt-1 text-[11px] text-gray-400">
                未获取到音色(检查 DubbingX API Key / 是否有自定义音色)
              </p>
            )}
          </div>

          {/* 情绪:类型 / 风格 / 档位 */}
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs font-semibold text-gray-600">情绪类型</label>
              <select
                value={emoType}
                onChange={(e) => {
                  setEmoType(e.target.value);
                  setAura("");
                }}
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
              >
                <option value="">自动(留空)</option>
                {emotions.map((e) => (
                  <option key={e.type} value={e.type}>
                    {e.type}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">风格</label>
              <select
                value={aura}
                onChange={(e) => setAura(e.target.value)}
                disabled={!emoType}
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-100"
              >
                <option value="">--</option>
                {auras.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">档位</label>
              <select
                value={level}
                onChange={(e) => setLevel(parseInt(e.target.value, 10))}
                disabled={!emoType}
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-100"
              >
                {[1, 2, 3].map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleAnalyze}
              disabled={analyzing || !text.trim()}
              className="rounded border border-indigo-300 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 disabled:opacity-40"
            >
              {analyzing ? "分析中…" : "🔍 分析情绪(回填)"}
            </button>
            <span className="text-xs text-gray-400">
              最终 emotion ={" "}
              <span className="font-mono text-indigo-600">
                {emotionString || "(空,自动识别)"}
              </span>
            </span>
          </div>

          {/* 语速 / 语调 / 音量 */}
          <div className="grid grid-cols-3 gap-3">
            <Slider
              label={`语速 ${speed.toFixed(2)}`}
              min={0.5}
              max={2}
              step={0.05}
              value={speed}
              onChange={setSpeed}
            />
            <Slider
              label={`语调 ${pitch.toFixed(2)}`}
              min={0.5}
              max={2}
              step={0.05}
              value={pitch}
              onChange={setPitch}
            />
            <Slider
              label={`音量 ${volume}dB`}
              min={-12}
              max={12}
              step={1}
              value={volume}
              onChange={setVolume}
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-600">文本</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
            />
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-1 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={autoPause}
                onChange={(e) => setAutoPause(e.target.checked)}
              />
              autoPause 自动停顿
            </label>
            <label className="flex items-center gap-1 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={align}
                onChange={(e) => setAlign(e.target.checked)}
              />
              ATA 字幕打轴
            </label>
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !text.trim() || !voiceId}
            className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
          >
            {loading
              ? "合成中…(DubbingX 轮询 + 可选打轴,约 10-60s)"
              : "▶ 生成试听"}
          </button>
        </div>

        {/* 结果 */}
        {result && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
            {lastParams && (
              <details className="mb-2 rounded bg-gray-50 p-2 text-[11px]" open>
                <summary className="cursor-pointer font-semibold text-gray-600">
                  本次传入参数(debug-synthesize body)
                </summary>
                <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap text-gray-700">
                  {JSON.stringify(lastParams, null, 2)}
                </pre>
              </details>
            )}
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-800">试听结果</span>
              <span className="text-xs text-gray-400">
                emotion={result.emotion_used}
                {result.duration != null && ` · ${result.duration.toFixed(1)}s`}
              </span>
            </div>
            <audio
              ref={audioRef}
              src={api.audioUrl(result.audio_url)}
              controls
              onTimeUpdate={() => {
                const el = audioRef.current;
                if (el) setActiveMs(el.currentTime * 1000);
              }}
              className="w-full"
            />
            {result.subtitles.length > 0 && (
              <div className="mt-2 max-h-60 overflow-y-auto rounded border border-gray-100 bg-gray-50 p-1.5">
                {result.subtitles.map((seg, i) => (
                  <div
                    key={i}
                    className={`flex cursor-pointer gap-2 rounded px-1.5 py-1 text-xs hover:bg-white ${
                      activeMs != null &&
                      activeMs >= seg.start_ms &&
                      activeMs < seg.end_ms
                        ? "bg-indigo-100 text-indigo-700"
                        : "text-gray-700"
                    }`}
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.currentTime = seg.start_ms / 1000;
                        audioRef.current.play();
                      }
                    }}
                  >
                    <span className="shrink-0 font-mono text-[10px] text-gray-400">
                      {fmtMs(seg.start_ms)}
                    </span>
                    <span className="leading-snug">{seg.text}</span>
                  </div>
                ))}
              </div>
            )}
            {autoPause && result.text_used !== text && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-gray-500">
                  查看 autoPause 处理后文本(含 break 标签)
                </summary>
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-[11px] text-gray-600">
                  {result.text_used}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* 历史对比 */}
        {history.length > 0 && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
            <span className="text-sm font-semibold text-gray-800">
              历史对比(本会话,最多 10 条)
            </span>
            <div className="mt-2 space-y-2">
              {history.map((h, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 rounded border border-gray-100 px-2 py-1.5"
                >
                  <span className="flex-1 font-mono text-[11px] text-gray-500">
                    {h.label}
                  </span>
                  <audio
                    src={api.audioUrl(h.result.audio_url)}
                    controls
                    className="h-8 max-w-[320px]"
                  />
                  <button
                    onClick={() => {
                      setResult(h.result);
                      setActiveMs(null);
                    }}
                    className="rounded px-2 py-0.5 text-[11px] text-indigo-600 hover:bg-indigo-50"
                  >
                    加载
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Slider({
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="text-xs font-semibold text-gray-600">{label}</label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="mt-1 w-full"
      />
    </div>
  );
}
