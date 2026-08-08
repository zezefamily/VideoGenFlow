// 根路径:已登录则创建新会话并跳转;未登录跳登录页。
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, loading } = useAuth();
  const create = useMutation({
    mutationFn: () => api.createConversation(),
    onSuccess: (conv) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      router.replace(`/chat/${conv.id}`);
    },
  });

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    create.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, user]);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 bg-[#fcfcfc] px-4 text-center">
      <p className="text-sm text-slate-500">
        {loading ? "正在准备创作空间…" : "正在创建新会话…"}
      </p>
      <a
        href="/login"
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
      >
        进入登录页
      </a>
      <p className="text-xs text-slate-400">首次使用请登录；登录后会自动新建创作会话。</p>
    </div>
  );
}
