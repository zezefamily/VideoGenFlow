"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type {
  ProjectDetail,
  ScriptArtifact,
  StoryboardDetail,
  StoryboardArtifact,
} from "@/lib/types";

type Kind = "script" | "storyboard";

type AnyArtifact = (ScriptArtifact | StoryboardArtifact) & {
  is_active: boolean;
  version: number;
  id: string;
};

/**
 * 版本选择器:展示脚本或分镜的全部版本,支持回退/确认到任一历史版本。
 * kind=script 用作品接口;kind=storyboard 用分镜接口(Phase 3)。
 */
export function VersionSelector({
  convId,
  kind,
  activeVersionId,
}: {
  convId: string;
  kind: Kind;
  activeVersionId?: string;
}) {
  const qc = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const queryKey = [kind, convId] as const;
  const { data } = useQuery({
    queryKey,
    queryFn: (): Promise<ProjectDetail | StoryboardDetail> =>
      kind === "script"
        ? api.getProject(convId)
        : api.getStoryboard(convId),
    refetchOnWindowFocus: false,
  });

  const versions = ((data as { versions?: AnyArtifact[] })?.versions ?? []) as AnyArtifact[];
  if (versions.length <= 1) return null; // 只有一版,无需选择器

  const handleActivate = async (artifactId: string) => {
    setBusyId(artifactId);
    try {
      await api.activateVersion(artifactId);
      await qc.invalidateQueries({ queryKey: ["project", convId] });
      await qc.invalidateQueries({ queryKey: ["storyboard", convId] });
      await qc.invalidateQueries({ queryKey: ["messages", convId] });
    } catch (e) {
      alert("回退失败:" + (e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const label = kind === "script" ? "版本历史" : "分镜版本";
  return (
    <div className="border-t border-gray-100 bg-gray-50 px-4 py-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-800"
      >
        🕘 {label}（{versions.length} 版）
        <span className="text-gray-400">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <ul className="mt-2 space-y-1">
          {[...versions]
            .sort((a, b) => b.version - a.version)
            .map((v) => {
              const isActive = v.is_active || v.id === activeVersionId;
              const sub =
                kind === "script"
                  ? `${(v as ScriptArtifact).duration_sec ?? 0}s · ${
                      (v as ScriptArtifact).title ?? ""
                    }`
                  : `${(v as StoryboardArtifact).shot_count ?? 0} 镜 · ${
                      (v as StoryboardArtifact).aspect_ratio ?? ""
                    }`;
              return (
                <li
                  key={v.id}
                  className="flex items-center justify-between rounded px-2 py-1 text-xs hover:bg-white"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-gray-700">
                      v{v.version}
                    </span>
                    <span className="text-gray-400">{sub}</span>
                    {isActive && (
                      <span className="rounded bg-green-100 px-1.5 py-0.5 text-[10px] text-green-700">
                        当前
                      </span>
                    )}
                  </span>
                  {!isActive && (
                    <button
                      disabled={busyId !== null}
                      onClick={() => handleActivate(v.id)}
                      className="rounded px-2 py-0.5 text-[11px] text-indigo-600 hover:bg-indigo-50 disabled:opacity-40"
                    >
                      {busyId === v.id ? "切换中…" : "回退到此版本"}
                    </button>
                  )}
                </li>
              );
            })}
        </ul>
      )}
    </div>
  );
}
