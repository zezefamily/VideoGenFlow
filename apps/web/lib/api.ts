// API 调用封装。base url 由环境变量配置,默认本地后端。
// Phase 5:自动注入 Bearer token;401 清理会话并跳登录。

import type {
  ActivateResult,
  AudioTrack,
  Conversation,
  ConversationSummary,
  DebugTTSParams,
  DebugTTSResult,
  EmotionList,
  ImageList,
  Message,
  ProjectDetail,
  ScriptArtifact,
  StoryboardDetail,
  StoryboardImage,
  StyleOption,
  TTSGenerateParams,
  SendMessageResponse,
  VideoAnalysis,
  VideoAnalysisLatest,
  VideoRender,
  ShotVideoList,
  VoiceList,
} from "./types";
import { clearSession, getToken, type AuthUser } from "./auth";

const API_URL =
  // 后端开发服务默认绑定 127.0.0.1；避免浏览器将 localhost 优先解析到 ::1
  // 后与 IPv4-only uvicorn 断连。部署环境仍由 NEXT_PUBLIC_API_URL 覆盖。
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401) {
    // 会话失效:清理并跳登录
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("未登录");
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ---- 认证 ----
export const authApi = {
  register: (email: string, password: string, name?: string) =>
    req<{ token: string; user: AuthUser }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email: string, password: string) =>
    req<{ token: string; user: AuthUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => req<AuthUser>("/api/auth/me"),
};

// ---- 会话 ----
export const api = {
  listConversations: () => req<ConversationSummary[]>("/api/conversations"),

  createConversation: (title?: string) =>
    req<Conversation>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title: title ?? null }),
    }),

  getConversation: (id: string) =>
    req<Conversation>(`/api/conversations/${id}`),

  getActiveRun: (id: string) =>
    req<import("./types").ActiveRunResult>(`/api/conversations/${id}/active-run`),

  renameConversation: (id: string, title: string) =>
    req<Conversation>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (id: string) =>
    req<{ ok: boolean }>(`/api/conversations/${id}`, { method: "DELETE" }),

  exportConversation: (id: string) =>
    req<Record<string, unknown>>(`/api/conversations/${id}/export`),

  // ---- 消息 ----
  listMessages: (convId: string) =>
    req<Message[]>(`/api/conversations/${convId}/messages`),

  sendMessage: (convId: string, content: string) =>
    req<SendMessageResponse>(`/api/conversations/${convId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  // ---- 运行 ----
  cancelRun: (runId: string) =>
    req<{ ok: boolean; status: string }>(`/api/runs/${runId}/cancel`, {
      method: "POST",
    }),

  // SSE 流 URL:带 token 查询参数(EventSource 不能发自定义头)
  streamUrl: (runId: string) => {
    const token = getToken() || "";
    return `${API_URL}/api/runs/${runId}/stream?token=${encodeURIComponent(token)}`;
  },

  // ---- 作品与版本(Phase 2)----
  getProject: (convId: string) =>
    req<ProjectDetail>(`/api/conversations/${convId}/project`),

  // ---- 分镜与版本(Phase 3)----
  getStoryboard: (convId: string) =>
    req<StoryboardDetail>(`/api/conversations/${convId}/storyboard`),

  // 画风列表(生图时选择)
  getStyles: () => req<StyleOption[]>("/api/styles"),

  activateVersion: (artifactId: string) =>
    req<ActivateResult>(`/api/artifacts/${artifactId}/activate`, {
      method: "POST",
    }),

  // ---- 分镜图片(Phase 4)----
  getImages: (convId: string) =>
    req<ImageList>(`/api/conversations/${convId}/images`),

  generateImages: (convId: string) =>
    req<StoryboardImage[]>(`/api/conversations/${convId}/images/generate`, {
      method: "POST",
    }),

  cancelImages: (convId: string) =>
    req<{ cancelled: number; storyboards: string[] }>(
      `/api/conversations/${convId}/images/cancel`,
      { method: "POST" }
    ),

  regenerateImage: (imageId: string) =>
    req<StoryboardImage>(`/api/images/${imageId}/regenerate`, {
      method: "POST",
    }),

  // ---- 视频分析(抖音链接解析 / 做同款)----
  getVideoAnalysis: (convId: string) =>
    req<VideoAnalysisLatest>(`/api/conversations/${convId}/video-analysis`),

  getVideoAnalysisById: (analysisId: string) =>
    req<VideoAnalysis>(`/api/video-analyses/${analysisId}`),

  // 本地图静态服务前缀(拼 local_path 用)
  imageUrl: (localPath: string) => {
    if (/^https?:\/\//.test(localPath)) return localPath; // S3 等绝对 URL 原样
    return `${API_URL.replace(/\/$/, "")}${localPath}`;
  },

  // ---- 配音 + 字幕(成片管线)----
  getAudioTrack: (convId: string) =>
    req<AudioTrack | null>(`/api/conversations/${convId}/audio-track`),

  generateTTS: (convId: string, body?: TTSGenerateParams) =>
    req<AudioTrack>(`/api/conversations/${convId}/tts/generate`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),

  cancelTTS: (convId: string) =>
    req<{ cancelled: number; tracks: string[] }>(
      `/api/conversations/${convId}/tts/cancel`,
      { method: "POST" }
    ),

  regenerateTrack: (trackId: string) =>
    req<AudioTrack>(`/api/audio-tracks/${trackId}/regenerate`, {
      method: "POST" }
    ),

  // 本地音频静态服务前缀(/api/audio/{id}.mp3 -> 拼后端地址)
  audioUrl: (path: string) => {
    if (/^https?:\/\//.test(path)) return path;
    return `${API_URL.replace(/\/$/, "")}${path}`;
  },

  // ---- 视频成片(成片管线:静态分镜 + 音频 + 字幕 -> mp4)----
  getVideo: (convId: string) =>
    req<VideoRender | null>(`/api/conversations/${convId}/video`),

  renderVideo: (convId: string, renderMode: "image" | "video" = "image") =>
    req<VideoRender>(`/api/conversations/${convId}/video/render`, {
      method: "POST",
      body: JSON.stringify({ render_mode: renderMode }),
    }),

  getShotVideos: (convId: string) => req<ShotVideoList>(`/api/conversations/${convId}/shot-videos`),
  planShotVideos: (convId: string, strategy: "smart" | "all" | "custom", shot_indices: number[] = []) => req<{strategy:string;selected_shots:number[];estimated_cost:number}>(`/api/conversations/${convId}/shot-videos/plan`, { method: "POST", body: JSON.stringify({strategy, shot_indices}) }),
  generateShotVideos: (convId: string, strategy: "smart" | "all" | "custom", shot_indices: number[] = []) => req<ShotVideoList>(`/api/conversations/${convId}/shot-videos/generate`, { method: "POST", body: JSON.stringify({strategy, shot_indices, confirmed:true}) }),

  cancelVideo: (convId: string) =>
    req<{ cancelled: number; renders: string[] }>(
      `/api/conversations/${convId}/video/cancel`,
      { method: "POST" }
    ),

  regenerateVideo: (renderId: string) =>
    req<VideoRender>(`/api/video-renders/${renderId}/regenerate`, {
      method: "POST",
    }),

  // 本地视频静态服务前缀(/api/video/{id}.mp4 -> 拼后端地址)
  videoUrl: (path: string) => {
    if (/^https?:\/\//.test(path)) return path;
    return `${API_URL.replace(/\/$/, "")}${path}`;
  },

  // ---- 调试台(临时,不落库)----
  listVoices: (pageSize = 500, isMyModel?: boolean) =>
    req<VoiceList>(
      `/api/tts/voices?pageSize=${pageSize}${
        isMyModel != null ? `&is_my_model=${isMyModel}` : ""
      }`
    ),

  getEmotions: (voiceId: string) =>
    req<EmotionList>(`/api/tts/voices/${voiceId}/emotions`),

  debugSynthesize: (body: DebugTTSParams) =>
    req<DebugTTSResult>(`/api/tts/debug-synthesize`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  analyzeEmotion: (text: string) =>
    req<{ emotion: string }>(`/api/tts/analyze-emotion`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
};
