"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getTTSProvider, VOLC_DEFAULT_TTS, type TTSProvider } from "@/lib/tts-settings";
import type { AudioTrack, ImageList, ScriptArtifact, ShotVideoList, StoryboardArtifact, VideoAnalysis, VideoRender } from "@/lib/types";
import { RenderModeModal } from "@/components/artifacts/RenderModeModal";

type Props = {
  convId: string;
  script: ScriptArtifact | null;
  storyboard: StoryboardArtifact | null;
  analysis?: VideoAnalysis | null;
  images?: ImageList;
  audio: AudioTrack | null;
  video: VideoRender | null;
  shotVideos: ShotVideoList | null;
  isWorking?: boolean;
  workingLabel?: string | null;
  onSend: (text: string) => void;
};

export function WorkflowDock({ convId, script, storyboard, analysis, images, audio, video, shotVideos, isWorking = false, workingLabel, onSend }: Props) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [submittedAction, setSubmittedAction] = useState<string | null>(null);
  const [ttsProvider, setProvider] = useState<TTSProvider>("volcengine");
  const [renderModal, setRenderModal] = useState(false);

  useEffect(() => {
    setProvider(getTTSProvider());
    const listener = (event: Event) => setProvider((event as CustomEvent<TTSProvider>).detail);
    window.addEventListener("tts-provider-changed", listener);
    return () => window.removeEventListener("tts-provider-changed", listener);
  }, []);

  const refresh = () => ["images", "audio-track", "video-render", "shot-videos"].forEach((key) => qc.invalidateQueries({ queryKey: [key, convId] }));
  const doTts = async () => {
    setBusy(true);
    try {
      await api.generateTTS(convId, ttsProvider === "volcengine" ? { provider: "volcengine", voice_id: VOLC_DEFAULT_TTS.voiceId, emotion: VOLC_DEFAULT_TTS.emotion, audio_speed: VOLC_DEFAULT_TTS.speed, audio_pitch: VOLC_DEFAULT_TTS.pitch, audio_volume: VOLC_DEFAULT_TTS.volume } : { provider: "dubbingx" });
      refresh();
    } finally { setBusy(false); }
  };
  const doVideo = async (mode: "image" | "video" = "image") => { setBusy(true); try { await api.renderVideo(convId, mode); refresh(); } finally { setBusy(false); } };

  const storyboardCurrent = !!storyboard && (!storyboard.script_version_id || storyboard.script_version_id === script?.id);
  const currentImages = storyboardCurrent ? images?.images.filter((item) => item.storyboard_version_id === storyboard?.id) ?? [] : [];
  const imgDone = currentImages.length > 0 && currentImages.every((item) => item.status === "done");
  const audioCurrent = !!audio && audio.script_version_id === script?.id;
  const videoCurrent = !!video && audioCurrent && video.audio_track_id === audio?.id && video.storyboard_version_id === storyboard?.id;
  const audioBusy = audio?.status === "pending" || audio?.status === "generating";
  const videoBusy = video?.status === "pending" || video?.status === "generating";
  const shotVideoBusy = !!shotVideos?.has_active;
  const shotVideoDone = (shotVideos?.assets.filter(item => item.status === "done").length || 0);
  let title = "告诉我你的创作方向", detail = "可以发链接、话题或一段口播文案。", primary = "", secondary = "";
  let action: (() => void) | undefined;
  let secondaryAction: (() => void) | undefined;

  if (shotVideoBusy) { title = "正在生成分镜视频"; detail = `Seedance 2.0 mini 正在生成 480p 无声视频，已完成 ${shotVideoDone}/${shotVideos?.assets.length || 0}。`; }
  else if (shotVideos?.assets.length && !shotVideoBusy && shotVideoDone > 0 && (!videoCurrent || video?.render_mode !== "video")) { title = "分镜视频已经准备好"; detail = `${shotVideoDone} 个动态镜头可用，失败镜头将自动回退为图片。`; primary = "合成视频成片"; action = () => doVideo("video"); }
  else if (videoBusy && videoCurrent) { title = "正在合成成片"; detail = video?.stage === "ffmpeg" ? "正在拼接画面、配音与字幕。" : "正在对齐分镜与字幕。"; }
  else if (audioBusy && audioCurrent) { title = "正在生成配音"; detail = audio?.stage === "ata" ? "正在为音频生成字幕时间轴。" : "正在合成配音。"; }
  else if (audio?.status === "error" && audioCurrent) { title = "配音生成失败"; detail = audio.error || "配音服务暂时不可用，请重试。"; primary = "重新生成配音"; action = doTts; }
  else if (video?.status === "done" && videoCurrent) { title = "成片已完成"; detail = `${video.duration_sec?.toFixed(1) || ""} 秒 · 已使用最新配音完成合成。`; primary = "查看成片"; action = () => window.open(api.videoUrl(video.video_url || ""), "_blank"); secondary = "重新合成"; secondaryAction = () => doVideo(video.render_mode === "video" ? "video" : "image"); }
  else if (!storyboardCurrent && script) { title = "脚本已更新"; detail = "当前分镜仍基于旧脚本，需要重新生成分镜后才能继续制作。"; primary = "确认，重新生成分镜"; action = () => onSend("基于当前脚本重新生成分镜"); }
  else if (audio?.status === "done" && audioCurrent && imgDone && !videoCurrent) { title = "新配音已经完成"; detail = "请选择使用图片还是生成动态视频后合成。"; primary = "选择成片方式"; action = () => setRenderModal(true); secondary = "重新生成配音"; secondaryAction = doTts; }
  else if (audio?.status === "done" && audioCurrent && imgDone) { title = "素材已经齐备"; detail = "请选择图片成片，或使用 Seedance 生成视频成片。"; primary = "选择成片方式"; action = () => setRenderModal(true); secondary = "修改分镜"; }
  else if (imgDone) { title = "分镜图已完成"; detail = `下一步使用${ttsProvider === "volcengine" ? "豆包语音 · 爽快思思" : "DubbingX"}生成配音与字幕。`; primary = "生成配音"; action = doTts; secondary = "修改分镜"; }
  else if (images?.has_active && storyboardCurrent) { title = "正在生成分镜图"; detail = "图片会逐张完成，你可以留在此处或稍后回来。"; }
  else if (storyboard) { title = "分镜已确认"; detail = "镜头已经排好。要我继续生成分镜图，还是先修改某个镜头？"; primary = "确认，生成分镜图"; action = () => onSend("继续生成分镜图"); secondary = "修改分镜"; }
  else if (analysis?.status === "analyzing" || analysis?.status === "pending") { title = "我正在拆解参考视频"; detail = "正在提取口播、分析钩子和叙事结构。"; }
  else if (analysis?.script) { title = "同款文案已经准备好"; detail = "要继续拆成分镜吗？"; primary = "确认，生成分镜"; action = () => onSend("继续生成分镜"); secondary = "修改文案"; }
  else if (analysis?.status === "done") { title = "参考视频已经拆解完成"; detail = "要开始创作同款文案吗？"; primary = "确认，生成同款文案"; action = () => onSend("请基于刚才的分析生成同款原创口播脚本"); }
  else if (script) { title = "脚本已确认"; detail = "要我继续拆成分镜，还是先调整这版表达？"; primary = "确认，生成分镜"; action = () => onSend("继续生成分镜"); secondary = "修改脚本"; }

  useEffect(() => setSubmittedAction(null), [primary]);
  const isViewAction = primary === "查看成片";
  const submitting = busy || isWorking || !!submittedAction;
  const submitPrimary = () => { if (!action || submitting) return; setSubmittedAction(primary); action(); };
  const editSecondary = () => onSend(secondary === "修改脚本" || secondary === "修改文案" ? "我想修改当前脚本：" : "我想修改当前分镜：");

  return (
    <section className="mx-auto w-full max-w-3xl px-4 pb-3">
      <div className="rounded-2xl border border-indigo-100 bg-white p-4 shadow-[0_8px_30px_rgba(79,70,229,0.08)]">
        <div className="flex items-start gap-3"><span className="mt-0.5 text-base text-indigo-600">✦</span><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-800">{isWorking ? workingLabel || "正在处理你的确认" : title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{isWorking ? "任务已启动，完成后我会带着结果回来请你确认下一步。" : detail}</p></div></div>
        {(submittedAction || isWorking) && <div className="mt-3 flex items-center gap-2 text-xs text-indigo-600"><span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />{workingLabel || "正在启动任务…"}</div>}
        {primary && <div className="mt-3 flex flex-wrap gap-2"><button disabled={isViewAction ? false : submitting} onClick={isViewAction ? action : submitPrimary} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-indigo-300">{isViewAction ? primary : submittedAction || isWorking ? "已确认，处理中…" : primary}</button>{secondary && <button disabled={submitting} onClick={secondaryAction || editSecondary} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50">{secondary}</button>}</div>}
      </div>
      {storyboard && <RenderModeModal open={renderModal} onClose={()=>setRenderModal(false)} convId={convId} storyboard={storyboard} onStarted={refresh}/>}
    </section>
  );
}
