"use client";

import { useEffect, useRef } from "react";
import type {
  Message,
  NodeState,
  ScriptArtifact,
  StoryboardArtifact,
  StoryboardImage,
  VideoAnalysis,
} from "@/lib/types";
import { ScriptCard } from "@/components/artifacts/ScriptCard";
import { StoryboardCard } from "@/components/artifacts/StoryboardCard";
import { ImageGallery } from "@/components/artifacts/ImageGallery";
import { VideoAnalysisCard } from "@/components/artifacts/VideoAnalysisCard";
import { RunProgress } from "./RunProgress";
import { WelcomePanel } from "./WelcomePanel";

function MessageBubble({
  msg,
  onEdit,
  onGenerateStoryboard,
  onGenerateImages,
  convId,
  isLatestScript,
  isLatestStoryboard,
  activeArtifact,
  activeStoryboard,
  onSend,
  onWelcomeChoose,
}: {
  msg: Message;
  onEdit?: () => void;
  onGenerateStoryboard?: (aspectRatio: string, style: string) => void;
  onGenerateImages?: (style: string) => void;
  convId?: string;
  isLatestScript?: boolean;
  isLatestStoryboard?: boolean;
  activeArtifact?: ScriptArtifact | null;
  activeStoryboard?: StoryboardArtifact | null;
  onSend?: (text: string) => void;
  onWelcomeChoose?: (text: string) => void;
}) {
  const isUser = msg.role === "user";
  // 最新脚本卡片:回退后用作品的激活版本展示,并挂版本选择器
  const scriptToShow =
    isLatestScript && activeArtifact ? activeArtifact : msg.artifact;
  // 最新分镜卡片:同理
  const storyboardToShow =
    isLatestStoryboard && activeStoryboard ? activeStoryboard : msg.storyboard;

  return (
    <div className={"flex " + (isUser ? "justify-end" : "justify-start")}>
      <div
        className={
          "max-w-[80%] " +
          (isUser
            ? "rounded-2xl bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm"
            : "w-full max-w-[86%]")
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : msg.message_type === "agent_welcome" && onWelcomeChoose ? (
          <WelcomePanel onChoose={onWelcomeChoose} />
        ) : msg.message_type === "script_card" && scriptToShow ? (
          <div>
            <p className="mb-1 text-sm text-gray-700">{msg.content}</p>
            <ScriptCard
              artifact={scriptToShow}
              onEdit={onEdit}
              onGenerateStoryboard={
                isLatestScript ? onGenerateStoryboard : undefined
              }
              convId={convId}
              showVersionSelector={isLatestScript && !!convId}
            />
          </div>
        ) : msg.message_type === "storyboard_card" && storyboardToShow ? (
          <div>
            <p className="mb-1 text-sm text-gray-700">{msg.content}</p>
            <StoryboardCard
              artifact={storyboardToShow}
              onEdit={onEdit}
              onGenerateImages={
                isLatestStoryboard ? onGenerateImages : undefined
              }
              convId={convId}
              showVersionSelector={isLatestStoryboard && !!convId}
            />
          </div>
        ) : msg.message_type === "image_gallery" && convId ? (
          <div>
            <p className="mb-1 text-sm text-gray-700">{msg.content}</p>
            <ImageGallery convId={convId} />
          </div>
        ) : msg.message_type === "video_analysis_card" ? (
          <div>
            <p className="mb-1 text-sm text-gray-700">{msg.content}</p>
            <VideoAnalysisCard
              analysisId={msg.artifact_id || undefined}
              onGenerateStoryboard={onGenerateStoryboard}
            />
          </div>
        ) : msg.message_type === "error" ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            ⚠️ {msg.content}
          </p>
        ) : (
          <p className="whitespace-pre-wrap text-sm text-gray-800">
            {msg.content}
          </p>
        )}
      </div>
    </div>
  );
}

export interface StreamingState {
  isStreaming: boolean;
  text: string;
  nodes: NodeState[];
  artifact: ScriptArtifact | null;
  storyboard: StoryboardArtifact | null;
  images: StoryboardImage[] | null;
  video_analysis: VideoAnalysis | null;
  error: string | null;
}

export function MessageList({
  messages,
  streaming,
  onEditScript,
  onGenerateStoryboard,
  onGenerateImages,
  convId,
  activeArtifact,
  activeStoryboard,
  onSend,
  onWelcomeChoose,
}: {
  messages: Message[];
  streaming: StreamingState;
  onEditScript?: () => void;
  onGenerateStoryboard?: (aspectRatio: string, style: string) => void;
  onGenerateImages?: (style: string) => void;
  convId?: string;
  activeArtifact?: ScriptArtifact | null;
  activeStoryboard?: StoryboardArtifact | null;
  onSend?: (text: string) => void;
  onWelcomeChoose?: (text: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 最后一条脚本/分镜卡片的位置(挂版本选择器 + 用激活版本展示)
  let lastScriptIdx = -1;
  let lastStoryboardIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    const t = messages[i].message_type;
    if (lastScriptIdx < 0 && t === "script_card") lastScriptIdx = i;
    if (lastStoryboardIdx < 0 && t === "storyboard_card") lastStoryboardIdx = i;
    if (lastScriptIdx >= 0 && lastStoryboardIdx >= 0) break;
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming.text, streaming.nodes.length]);

  return (
    <div className="mx-auto flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        {messages.map((m, i) => (
          <MessageBubble
            key={m.id}
            msg={m}
            onEdit={onEditScript}
            onGenerateStoryboard={onGenerateStoryboard}
            onGenerateImages={onGenerateImages}
            convId={convId}
            isLatestScript={i === lastScriptIdx}
            isLatestStoryboard={i === lastStoryboardIdx}
            activeArtifact={activeArtifact}
            activeStoryboard={activeStoryboard}
            onSend={onSend}
            onWelcomeChoose={onWelcomeChoose}
          />
        ))}

        {streaming.isStreaming && (
          <div className="flex justify-start">
            <div className="w-full max-w-[80%]">
              <RunProgress nodes={streaming.nodes} />
              {streaming.artifact && (
                <ScriptCard artifact={streaming.artifact} onEdit={onEditScript} />
              )}
              {streaming.storyboard && (
                <StoryboardCard
                  artifact={streaming.storyboard}
                  onEdit={onEditScript}
                />
              )}
              {streaming.images && convId && (
                <ImageGallery convId={convId} streamingImages={streaming.images} />
              )}
              {streaming.video_analysis && (
                <VideoAnalysisCard
                  analysisId={streaming.video_analysis.id}
                  initial={streaming.video_analysis}
                  onGenerateStoryboard={onGenerateStoryboard}
                />
              )}
              {streaming.text && (
                <p className="whitespace-pre-wrap text-sm text-gray-800">
                  {streaming.text}
                  <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-gray-400 align-middle" />
                </p>
              )}
              {streaming.error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                  ⚠️ {streaming.error}
                </p>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
