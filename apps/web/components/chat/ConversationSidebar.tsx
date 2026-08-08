"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TTSSettingsModal } from "@/components/settings/TTSSettingsModal";

export function ConversationSidebar({
  activeId,
}: {
  activeId: string | null;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, logout } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: api.listConversations,
  });

  const create = useMutation({
    mutationFn: () => api.createConversation(),
    onSuccess: (conv) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      router.push(`/chat/${conv.id}`);
    },
  });

  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.renameConversation(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const onRename = (id: string, oldTitle: string) => {
    const title = window.prompt("重命名会话", oldTitle);
    if (title && title.trim() && title !== oldTitle) {
      rename.mutate({ id, title: title.trim() });
    }
  };

  const onDelete = (id: string) => {
    if (window.confirm("删除该会话?")) {
      remove.mutate(id);
      if (id === activeId) router.push("/");
    }
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r border-gray-200 bg-white">
      <div className="p-3">
        <button
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          + 新建会话
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {conversations.length === 0 && (
          <p className="px-2 py-4 text-center text-xs text-gray-400">
            还没有会话
          </p>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={
              "group mb-1 flex items-center rounded-md px-2 py-2 text-sm cursor-pointer " +
              (c.id === activeId
                ? "bg-indigo-50 text-indigo-700"
                : "text-gray-700 hover:bg-gray-100")
            }
            onClick={() => router.push(`/chat/${c.id}`)}
          >
            <span className="flex-1 truncate">{c.title || "新会话"}</span>
            <span className="hidden gap-1 group-hover:flex">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRename(c.id, c.title);
                }}
                className="text-gray-400 hover:text-indigo-600"
                title="重命名"
              >
                ✏️
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
                className="text-gray-400 hover:text-red-600"
                title="删除"
              >
                🗑️
              </button>
            </span>
          </div>
        ))}
      </nav>

      <div className="border-t border-gray-200 p-3">
        <button onClick={() => setSettingsOpen(true)} className="mb-2 w-full rounded-md px-2 py-1.5 text-left text-xs text-slate-600 hover:bg-slate-100">⚙️ 配音设置</button>
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="truncate text-gray-600" title={user?.email || ""}>
            {user?.email || "未登录"}
          </span>
          <button
            onClick={() => {
              logout();
              qc.clear();
              router.replace("/login");
            }}
            className="text-gray-400 hover:text-red-600"
            title="退出登录"
          >
            退出
          </button>
        </div>
        <div className="text-[11px] text-gray-400">VideoGenFlow · Phase 5</div>
      </div>
      <TTSSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </aside>
  );
}
