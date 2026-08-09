"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { streamRun } from "@/lib/sse";
import { useAuth } from "@/lib/auth";
import type {
  Message,
  Conversation,
  ConversationSummary,
} from "@/lib/types";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { MessageList, type StreamingState } from "@/components/chat/MessageList";
import { Composer } from "@/components/chat/Composer";
import { WorkflowDock } from "@/components/chat/WorkflowDock";

export default function ChatPage({
  params,
}: {
  params: { conversationId: string };
}) {
  const convId = params.conversationId;
  const qc = useQueryClient();
  const router = useRouter();
  const { user, loading } = useAuth();

  const { data: conv } = useQuery({
    queryKey: ["conversation", convId],
    queryFn: () => api.getConversation(convId),
    enabled: !!user,
  });

  const { data: messages = [] } = useQuery({
    queryKey: ["messages", convId],
    queryFn: () => api.listMessages(convId),
    enabled: !!user,
  });

  const { data: activeRun } = useQuery({
    queryKey: ["active-run", convId],
    queryFn: () => api.getActiveRun(convId),
    enabled: !!user,
    refetchInterval: (q) => (q.state.data?.run ? 1500 : false),
  });

  // 当前作品的激活版本(Phase 2):回退后最新脚本卡片改用它展示
  const { data: project } = useQuery({
    queryKey: ["project", convId],
    queryFn: () => api.getProject(convId),
    refetchOnWindowFocus: false,
    enabled: !!user,
  });

  const { data: videoAnalysis } = useQuery({
    queryKey: ["video-analysis", convId],
    queryFn: () => api.getVideoAnalysis(convId),
    enabled: !!user,
    refetchInterval: (q) =>
      q.state.data?.has_active ? 3000 : false,
  });

  // 当前作品的激活分镜(Phase 3):回退后最新分镜卡片改用它展示
  const { data: storyboardDetail } = useQuery({
    queryKey: ["storyboard", convId],
    queryFn: () => api.getStoryboard(convId),
    refetchOnWindowFocus: false,
    enabled: !!user,
  });
  const { data: audioTrack } = useQuery({
    queryKey: ["audio-track", convId],
    queryFn: () => api.getAudioTrack(convId),
    enabled: !!user,
    refetchInterval: (q) => (q.state.data?.has_active ? 3000 : false),
  });
  const { data: videoRender } = useQuery({
    queryKey: ["video-render", convId],
    queryFn: () => api.getVideo(convId),
    enabled: !!user,
    refetchInterval: (q) => (q.state.data?.has_active ? 3000 : false),
  });
  const { data: shotVideos } = useQuery({
    queryKey: ["shot-videos", convId], queryFn: () => api.getShotVideos(convId), enabled: !!user,
    refetchInterval: (q) => q.state.data?.has_active ? 5000 : false,
  });
  const { data: imageList } = useQuery({
    queryKey: ["images", convId],
    queryFn: () => api.getImages(convId),
    enabled: !!user && !!storyboardDetail?.active,
    refetchInterval: (q) => (q.state.data?.has_active ? 3000 : false),
  });

  // 脚本产物一到就同步侧栏与页头缓存，避免用户必须刷新才能看到新标题。
  const syncConversationTitle = (title?: string | null) => {
    const nextTitle = title?.trim();
    if (!nextTitle) return;
    qc.setQueryData<Conversation>(["conversation", convId], (old) =>
      old ? { ...old, title: nextTitle } : old
    );
    qc.setQueryData<ConversationSummary[]>(["conversations"], (old = []) =>
      old.map((item) =>
        item.id === convId ? { ...item, title: nextTitle } : item
      )
    );
  };

  useEffect(() => {
    syncConversationTitle(
      project?.active?.title || videoAnalysis?.analysis?.script?.title
    );
  }, [project?.active?.title, videoAnalysis?.analysis?.script?.title]);

  // 未登录跳登录页
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
    text: "",
    nodes: [],
    artifact: null,
    storyboard: null,
    images: null,
    video_analysis: null,
    error: null,
  });
  const [agentStatus, setAgentStatus] = useState<string | null>(null);
  const closeRef = useRef<(() => void) | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  // 离开页面时关闭 SSE
  useEffect(() => {
    return () => closeRef.current?.();
  }, []);

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-500">
        加载中…
      </div>
    );
  }

  const idle: StreamingState = {
    isStreaming: false,
    text: "",
    nodes: [],
    artifact: null,
    storyboard: null,
    images: null,
    video_analysis: null,
    error: null,
  };

  const send = async (text: string) => {
    // 乐观更新:用户消息立即上屏,不等后端落库
    // (否则要等 AI 整段响应完成、onMessageSaved 时才随 invalidate 一起出现)
    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      conversation_id: convId,
      role: "user",
      content: text,
      message_type: "text",
      artifact_id: null,
      status: "complete",
      metadata_json: null,
      created_at: new Date().toISOString(),
      artifact: null,
      storyboard: null,
    };
    qc.setQueryData<Message[]>(["messages", convId], (old = []) => [
      ...(old ?? []),
      optimisticMsg,
    ]);

    setAgentStatus("正在理解你的需求");
    setStreaming({ ...idle, isStreaming: true });
    try {
      const { run_id } = await api.sendMessage(convId, text);
      closeRef.current = streamRun(run_id, {
        onToken: (t) =>
          setStreaming((s) => ({ ...s, text: s.text + t })),
        onNodeStart: (node, label) =>
          setStreaming((s) => ({
            ...s,
            nodes: s.nodes.some((item) => item.node === node)
              ? s.nodes.map((item) => item.node === node ? { ...item, label, status: "running" } : item)
              : [...s.nodes, { node, label, status: "running" }],
          })),
        onNodeEnd: (node) =>
          setStreaming((s) => ({
            ...s,
            nodes: s.nodes.map((n) =>
              n.node === node ? { ...n, status: "done" } : n
            ),
          })),
        onAgentStatus: setAgentStatus,
        onArtifact: ({ script, storyboard, images, video_analysis, audio, video }) => {
          syncConversationTitle(script?.title || video_analysis?.script?.title);
          if (audio) qc.setQueryData(["audio-track", convId], { ...audio, has_active: true });
          if (video) qc.setQueryData(["video-render", convId], { ...video, has_active: true });
          setStreaming((s) => ({
            ...s,
            artifact: script ?? s.artifact,
            storyboard: storyboard ?? s.storyboard,
            images: images ?? s.images,
            video_analysis: video_analysis ?? s.video_analysis,
          }));
        },
        onMessageSaved: () => {
          // 消息已落库:清掉流式气泡,展示持久化消息
          setAgentStatus(null);
          setStreaming(idle);
          qc.invalidateQueries({ queryKey: ["messages", convId] });
          qc.invalidateQueries({ queryKey: ["project", convId] });
          qc.invalidateQueries({ queryKey: ["storyboard", convId] });
          qc.invalidateQueries({ queryKey: ["images", convId] });
          qc.invalidateQueries({ queryKey: ["video-analysis", convId] });
          qc.invalidateQueries({ queryKey: ["audio-track", convId] });
          qc.invalidateQueries({ queryKey: ["video-render", convId] });
          qc.invalidateQueries({ queryKey: ["shot-videos", convId] });
        },
        onError: (e) => {
          setAgentStatus(null);
          setStreaming((s) => ({ ...s, isStreaming: false, error: e }));
        },
        onDone: () => {
          setAgentStatus(null);
          setStreaming(idle);
          qc.invalidateQueries({ queryKey: ["messages", convId] });
          qc.invalidateQueries({ queryKey: ["conversations"] });
          qc.invalidateQueries({ queryKey: ["project", convId] });
          qc.invalidateQueries({ queryKey: ["storyboard", convId] });
          qc.invalidateQueries({ queryKey: ["images", convId] });
          qc.invalidateQueries({ queryKey: ["video-analysis", convId] });
          qc.invalidateQueries({ queryKey: ["audio-track", convId] });
          qc.invalidateQueries({ queryKey: ["video-render", convId] });
          qc.invalidateQueries({ queryKey: ["shot-videos", convId] });
        },
      });
    } catch (e: any) {
      setStreaming({ ...idle, error: e?.message || "发送失败" });
      // 发送失败:拉取真实状态,移除乐观消息
      qc.invalidateQueries({ queryKey: ["messages", convId] });
    }
  };

  const onEditScript = () => {
    setDraft("");
    composerRef.current?.focus();
  };

  const onGenerateStoryboard = (aspectRatio: string, style: string) => {
    send(`用${style}生成${aspectRatio}分镜`);
  };

  const onGenerateImages = (style: string) => {
    send(`用${style}生成分镜图`);
  };

  return (
    <div className="flex h-screen">
      <ConversationSidebar activeId={convId} />

      <main className="flex flex-1 flex-col">
        <header className="flex items-center border-b border-slate-200 bg-white px-5 py-3">
          <div><p className="text-[10px] font-medium tracking-widest text-indigo-600">CREATIVE AGENT</p><h1 className="text-sm font-semibold text-slate-800">
            {conv?.title || "新会话"}
          </h1></div>
        </header>

        <MessageList
          messages={messages}
          streaming={streaming}
          onEditScript={onEditScript}
          onGenerateStoryboard={onGenerateStoryboard}
          onGenerateImages={onGenerateImages}
          convId={convId}
          activeArtifact={project?.active ?? null}
          activeStoryboard={storyboardDetail?.active ?? null}
          onSend={send}
          shotVideos={shotVideos ?? null}
          onWelcomeChoose={(text) => {
            setDraft(text);
            requestAnimationFrame(() => composerRef.current?.focus());
          }}
        />

        <WorkflowDock
          convId={convId}
          script={project?.active ?? null}
          storyboard={storyboardDetail?.active ?? null}
          analysis={videoAnalysis?.analysis ?? null}
          images={imageList}
          audio={audioTrack ?? null}
          video={videoRender ?? null}
          shotVideos={shotVideos ?? null}
          isWorking={streaming.isStreaming || !!activeRun?.run}
          workingLabel={agentStatus || activeRunLabel(activeRun?.run?.current_node)}
          onSend={send}
        />

        <Composer
          onSend={send}
          disabled={streaming.isStreaming}
          draft={draft}
          setDraft={setDraft}
          inputRef={composerRef}
        />
      </main>
    </div>
  );
}

function activeRunLabel(node?: string | null) {
  const labels: Record<string, string> = {
    load_context: "正在加载会话上下文",
    classify_intent: "正在理解你的需求",
    generate_script: "正在生成口播脚本",
    revise_script: "正在修改口播脚本",
    generate_storyboard: "正在生成分镜",
    revise_storyboard: "正在修改分镜",
    generate_images: "正在生成分镜图",
    analyze_video: "正在分析参考视频",
    generate_tts: "正在启动配音生成",
    render_video: "正在启动成片合成",
    respond: "正在组织回复",
  };
  return node ? labels[node] || "正在执行创作任务" : "正在启动创作任务";
}
