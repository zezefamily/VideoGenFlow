// SSE 客户端:订阅一次 run 的事件流。

import { api } from "./api";
import type { SSEEvent } from "./types";

export interface ArtifactPayload {
  script?: any;
  storyboard?: any;
  images?: any[];
  video_analysis?: any;
  audio?: any;
  video?: any;
}

export interface StreamHandlers {
  onToken: (text: string) => void;
  onNodeStart: (node: string, label: string) => void;
  onNodeEnd: (node: string, label: string) => void;
  onAgentStatus?: (label: string) => void;
  onArtifact: (payload: ArtifactPayload) => void;
  onMessageSaved: (message: any) => void;
  onError: (error: string) => void;
  onDone: (cancelled?: boolean) => void;
}

/**
 * 订阅 run 的事件流。返回一个关闭函数。
 * EventSource 仅支持 GET 且无法携带自定义 header,故 token 经 ?token= 查询参数传递
 * (api.streamUrl 已拼接)。
 */
export function streamRun(runId: string, handlers: StreamHandlers): () => void {
  const es = new EventSource(api.streamUrl(runId));

  es.onmessage = (e) => {
    let event: SSEEvent;
    try {
      event = JSON.parse(e.data);
    } catch {
      return;
    }
    const d = event.data || {};
    switch (event.type) {
      case "token":
        handlers.onToken(d.text || "");
        break;
      case "node_start":
        handlers.onNodeStart(d.node, d.label);
        break;
      case "node_end":
        handlers.onNodeEnd(d.node, d.label);
        break;
      case "agent_status":
        handlers.onAgentStatus?.(d.label || "正在处理");
        break;
      case "artifact":
        handlers.onArtifact({
          script: d.script,
          storyboard: d.storyboard,
          images: d.images,
          video_analysis: d.video_analysis,
          audio: d.audio,
          video: d.video,
        });
        break;
      case "message_saved":
        handlers.onMessageSaved(d.message);
        break;
      case "error":
        handlers.onError(d.error || "未知错误");
        break;
      case "done":
        handlers.onDone(d.cancelled === true);
        es.close();
        break;
    }
  };

  es.onerror = () => {
    // 浏览器会自动重连;若 run 已结束,服务端返回 404,这里兜底关闭
    es.close();
  };

  return () => es.close();
}
