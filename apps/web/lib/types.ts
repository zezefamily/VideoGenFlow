// 与后端 schema 对齐的类型定义。

export interface Conversation {
  id: string;
  title: string;
  thread_id: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string | null;
}

export interface ScriptArtifact {
  id: string;
  version: number;
  is_active: boolean;
  title: string;
  keywords: string[];
  duration_sec: number;
  content: string;
  golden_sentence: string | null;
  psychology_theory: string | null;
  interaction_guide: string | null;
  actions: string[];
}

// 作品(项目)与多版本(Phase 2)
export interface ProjectOut {
  id: string;
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  project: ProjectOut | null;
  versions: ScriptArtifact[];
  active: ScriptArtifact | null;
}

// 分镜(Phase 3)
export interface StoryboardShot {
  index: number;
  title: string;
  visual: string;
  video_prompt: string;
  narration: string;
  duration_sec: number;
  camera: string;
  notes: string;
}

export interface StoryboardArtifact {
  id: string;
  version: number;
  is_active: boolean;
  script_version_id: string | null;
  aspect_ratio: string;
  style: string | null;
  shots: StoryboardShot[];
  shot_count: number;
  total_duration_sec: number;
  actions: string[];
}

export interface StoryboardDetail {
  versions: StoryboardArtifact[];
  active: StoryboardArtifact | null;
}

// 画风选项(生图时选择)
export interface StyleOption {
  name: string;
  description: string;
}

// 分镜图片(Phase 4)
export interface StoryboardImage {
  id: string;
  storyboard_version_id: string;
  shot_index: number;
  status: "pending" | "generating" | "done" | "error" | "cancelled";
  method: string | null;
  prompt: string;
  image_url: string | null;
  local_path: string | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ImageList {
  images: StoryboardImage[];
  has_active: boolean;
}

// 视频分析(抖音链接解析 / 做同款)
export interface VideoAnalysis {
  id: string;
  conversation_id: string;
  project_id: string | null;
  share_link: string;
  status: "pending" | "analyzing" | "done" | "error";
  method: string | null; // subtitle | asr | failed
  video_info: Record<string, any> | null;
  transcript: string | null;
  analysis: Record<string, any> | null;
  script_version_id: string | null;
  script: ScriptArtifact | null; // 仿写脚本(完成后有)
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface VideoAnalysisLatest {
  analysis: VideoAnalysis | null;
  has_active: boolean;
}

export interface ActiveRun {
  id: string;
  status: "running";
  current_node: string | null;
  started_at: string | null;
}

export interface ActiveRunResult {
  run: ActiveRun | null;
}

// 激活(回退)接口的返回:自动识别脚本/分镜
export interface ActivateResult {
  type: "script" | "storyboard";
  script?: ScriptArtifact;
  storyboard?: StoryboardArtifact;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  message_type:
    | "text"
    | "script_card"
    | "storyboard_card"
    | "image_gallery"
    | "video_analysis_card"
    | "agent_welcome"
    | "tool_status"
    | "error";
  artifact_id: string | null;
  status: string;
  metadata_json: string | null;
  created_at: string;
  artifact: ScriptArtifact | null;
  storyboard: StoryboardArtifact | null;
}

export interface SendMessageResponse {
  run_id: string;
  message_id: string;
}

// SSE 事件
export type SSEEventType =
  | "token"
  | "node_start"
  | "node_end"
  | "node_error"
  | "agent_status"
  | "artifact"
  | "message_saved"
  | "error"
  | "done";

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, any>;
}

// 运行中的节点状态(前端展示用)
export interface NodeState {
  node: string;
  label: string;
  status: "running" | "done" | "error";
}

// 配音 + 字幕(成片管线)
export interface SubtitleWord {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface SubtitleSegment {
  order: number | null;
  text: string;
  start_ms: number;
  end_ms: number;
  words: SubtitleWord[];
}

export interface AudioTrack {
  id: string;
  conversation_id: string;
  project_id: string | null;
  script_version_id: string | null;
  status: "pending" | "generating" | "done" | "error" | "cancelled";
  stage: string | null; // tts | ata
  provider: "dubbingx" | "volcengine";
  voice_id: string;
  emotion: string | null;
  language: string;
  audio_speed: number;
  audio_pitch: number;
  audio_volume: number;
  file_format: string;
  script_text: string;
  tts_task_id: string | null;
  ata_task_id: string | null;
  audio_url: string | null;
  audio_duration_sec: number | null;
  subtitles: SubtitleSegment[];
  error: string | null;
  has_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// 视频成片(成片管线:静态分镜 + 音频 + 字幕 -> mp4)
export interface VideoRender {
  id: string;
  conversation_id: string;
  project_id: string | null;
  audio_track_id: string | null;
  storyboard_version_id: string | null;
  status: "pending" | "generating" | "done" | "error" | "cancelled";
  stage: string | null; // align | ffmpeg
  aspect_ratio: string;
  video_url: string | null;
  duration_sec: number | null;
  error: string | null;
  has_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// generateTTS 请求体(全可选,缺省用后端默认音色)
export interface TTSGenerateParams {
  provider?: "dubbingx" | "volcengine";
  voice_id?: string;
  emotion?: string;
  language?: string;
  audio_speed?: number;
  audio_pitch?: number;
  audio_volume?: number;
  file_format?: string;
}

// 音色 / 情绪(后续选择器用)
export interface Voice {
  id: string;
  name: string;
  grade: string | null;
  gender: number | null;
  description: string | null;
  avatar: string | null;
  voice_url: string | null;
  version: string | null;
  is_official: boolean | null;
}

export interface VoiceList {
  total: number;
  list: Voice[];
}

export interface Emotion {
  type: string;
  auras: string[];
}

export interface EmotionList {
  list: Emotion[];
}

// ---- 调试台(临时,不落库)----
export interface DebugTTSParams {
  text: string;
  voice_id: string;
  emotion?: string | null;
  language?: string;
  audio_speed?: number;
  audio_pitch?: number;
  audio_volume?: number;
  file_format?: string;
  auto_pause?: boolean;
  align?: boolean;
}

export interface DebugTTSResult {
  audio_url: string;
  duration: number | null;
  subtitles: SubtitleSegment[];
  emotion_used: string | null;
  text_used: string;
  task_id: string;
}
