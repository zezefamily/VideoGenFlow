"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { VideoAnalysis } from "@/lib/types";

const STATUS_META: Record<
  VideoAnalysis["status"],
  { label: string; cls: string }
> = {
  pending: { label: "等待中", cls: "bg-gray-100 text-gray-500" },
  analyzing: { label: "解析中", cls: "bg-blue-100 text-blue-600" },
  done: { label: "已完成", cls: "bg-green-100 text-green-700" },
  error: { label: "失败", cls: "bg-red-100 text-red-600" },
};

function MethodBadge({ method }: { method: string | null }) {
  if (!method || method === "failed") return null;
  const label = method === "subtitle" ? "字幕提取" : "语音识别";
  return (
    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] text-purple-700">
      {label}
    </span>
  );
}

function TopicTags({ topics }: { topics: string[] }) {
  if (!topics || topics.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {topics.slice(0, 10).map((t, i) => (
        <span
          key={i}
          className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600"
        >
          #{t}
        </span>
      ))}
    </div>
  );
}

function AnalysisSection({ analysis }: { analysis: Record<string, any> }) {
  const pain = analysis.pain_points as string[] | undefined;
  const golden = analysis.golden_sentences as string[] | undefined;
  const takeaways = analysis.takeaways as string[] | undefined;
  return (
    <div className="space-y-2 text-xs text-gray-700">
      {analysis.topic && (
        <div>
          <span className="font-medium text-gray-800">核心话题：</span>
          {analysis.topic}
        </div>
      )}
      {analysis.angle && (
        <div>
          <span className="font-medium text-gray-800">切入角度：</span>
          {analysis.angle}
        </div>
      )}
      {pain && pain.length > 0 && (
        <div>
          <span className="font-medium text-gray-800">受众痛点：</span>
          {pain.join("、")}
        </div>
      )}
      {analysis.hook && (
        <div>
          <span className="font-medium text-gray-800">钩子手法：</span>
          {analysis.hook}
        </div>
      )}
      {analysis.structure && (
        <div>
          <span className="font-medium text-gray-800">结构节奏：</span>
          {analysis.structure}
        </div>
      )}
      {golden && golden.length > 0 && (
        <div>
          <span className="font-medium text-gray-800">原视频金句：</span>
          <ul className="ml-4 list-disc">
            {golden.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}
      {takeaways && takeaways.length > 0 && (
        <div>
          <span className="font-medium text-gray-800">可借鉴手法：</span>
          <ul className="ml-4 list-disc">
            {takeaways.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      {analysis.audience && (
        <div>
          <span className="font-medium text-gray-800">目标受众：</span>
          {analysis.audience}
        </div>
      )}
      {analysis.emotion && (
        <div>
          <span className="font-medium text-gray-800">情绪曲线：</span>
          {analysis.emotion}
        </div>
      )}
    </div>
  );
}

/**
 * 视频分析卡片:展示爆款链接解析进度与产物(抖音做同款)。
 * 持久化消息按 analysisId 拉取;流式期用 initial 临时态,poll 同一 id 取后续进度。
 */
export function VideoAnalysisCard({
  analysisId,
  initial,
}: {
  analysisId?: string;
  initial?: VideoAnalysis | null;
  /** 行为统一由底部 Agent 确认卡承接，保留兼容旧消息渲染调用。 */
  onGenerateStoryboard?: (aspectRatio: string, style: string) => void;
}) {
  const { data } = useQuery({
    queryKey: ["video-analysis", analysisId],
    queryFn: () => api.getVideoAnalysisById(analysisId!),
    enabled: !!analysisId,
    refetchInterval: (q) =>
      q.state.data &&
      (q.state.data.status === "pending" ||
        q.state.data.status === "analyzing")
        ? 3000
        : false,
    refetchOnWindowFocus: false,
  });

  const va: VideoAnalysis | null | undefined = data ?? initial;
  if (!va) {
    return (
      <div className="mt-2 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-400">
        加载分析…
      </div>
    );
  }

  const meta = STATUS_META[va.status];
  const info = va.video_info || {};
  const topics: string[] = info.topics || [];
  const active = va.status === "pending" || va.status === "analyzing";

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">
            ✦ {active ? "正在拆解参考视频" : "参考视频拆解完成"}
          </span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${meta.cls}`}>
            {meta.label}
          </span>
          <MethodBadge method={va.method} />
          {active && (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
          )}
        </div>
        {info.duration ? (
          <span className="text-xs text-gray-500">
            时长 {Math.round(info.duration)}s
          </span>
        ) : null}
      </div>

      <div className="px-4 py-3">
        {/* 视频元信息 */}
        {(info.title || info.author || info.like_count) && (
          <div className="mb-2">
            {info.title && (
              <p className="text-sm font-medium text-gray-800">{info.title}</p>
            )}
            <p className="text-xs text-gray-500">
              {info.author ? `@${info.author}` : ""}
              {info.like_count ? ` · 👍 ${info.like_count}` : ""}
              {info.view_count ? ` · 播放 ${info.view_count}` : ""}
            </p>
            <TopicTags topics={topics} />
          </div>
        )}

        {/* 进行中提示 */}
        {active && (
          <p className="text-xs text-blue-600">
            正在下载视频、提取口播文案并拆解爆款手法…
          </p>
        )}

        {/* 错误 */}
        {va.status === "error" && va.error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
            ⚠️ {va.error}
          </p>
        )}

        {/* 文案(可折叠) */}
        {va.transcript && (
          <details className="mb-2 rounded-md bg-gray-50 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-gray-700">
              原视频口播文案
            </summary>
            <p className="mt-1 whitespace-pre-wrap text-xs leading-6 text-gray-600">
              {va.transcript}
            </p>
          </details>
        )}

        {/* 先给用户一条可读结论，完整拆解按需展开 */}
        {va.analysis && (
          <>
            <div className="rounded-lg bg-indigo-50/70 px-3 py-2.5 text-sm leading-6 text-slate-700">
              <span className="font-medium text-slate-900">核心判断：</span>
              {va.analysis.topic || va.analysis.angle || "已提炼出原视频的叙事结构与情绪钩子。"}
              {va.analysis.hook ? ` 以“${va.analysis.hook}”完成开场吸引。` : ""}
            </div>
            <details className="mt-2 rounded-lg border border-slate-100 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-slate-600">查看完整拆解</summary>
              <div className="mt-3"><AnalysisSection analysis={va.analysis} /></div>
            </details>
          </>
        )}

        {/* 仿写脚本 */}
        {va.script && (
          <div className="mt-3 rounded-md border border-indigo-100 bg-indigo-50/40 p-3">
            <p className="mb-1 text-xs font-semibold text-indigo-800">
              ✍️ 同款原创脚本
            </p>
            {va.script.title && (
              <p className="text-sm font-medium text-gray-800">
                {va.script.title}
              </p>
            )}
            <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-gray-800">{va.script.content.slice(0, 180)}{va.script.content.length > 180 ? "…" : ""}</p>
            {va.script.content.length > 180 && <details className="mt-2"><summary className="cursor-pointer text-xs font-medium text-indigo-600">查看完整文案</summary><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-gray-800">{va.script.content}</p></details>}
            {va.script.golden_sentence && (
              <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                💎 {va.script.golden_sentence}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
