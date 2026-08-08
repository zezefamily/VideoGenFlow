"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("dev@videogenflow.local");
  const [password, setPassword] = useState("devpassword");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setPending(true);
    try {
      const res =
        mode === "login"
          ? await authApi.login(email, password)
          : await authApi.register(email, password, name || undefined);
      setSession(res.token, res.user);
      router.replace("/");
    } catch (err) {
      setError(String(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-gray-900">
          VideoGenFlow
        </h1>
        <p className="mb-5 text-sm text-gray-500">
          爆款心理学短视频创作助手 ·{" "}
          {mode === "login" ? "登录" : "注册"}
        </p>

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <input
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              placeholder="昵称(可选)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          <input
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            placeholder="邮箱"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            placeholder="密码(至少 6 位)"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-600">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {pending ? "处理中…" : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>

        <div className="mt-4 text-center text-xs text-gray-500">
          {mode === "login" ? (
            <>
              没有账号?{" "}
              <button
                className="text-indigo-600 hover:underline"
                onClick={() => setMode("register")}
              >
                去注册
              </button>
            </>
          ) : (
            <>
              已有账号?{" "}
              <button
                className="text-indigo-600 hover:underline"
                onClick={() => setMode("login")}
              >
                去登录
              </button>
            </>
          )}
        </div>
        <p className="mt-3 text-center text-[11px] text-gray-400">
          开发默认账号:dev@videogenflow.local / devpassword
        </p>
      </div>
    </div>
  );
}
