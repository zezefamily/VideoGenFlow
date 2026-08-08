import type { NodeState } from "@/lib/types";

export function RunProgress({ nodes }: { nodes: NodeState[] }) {
  if (nodes.length === 0) return null;
  return (
    <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs">
      {nodes.map((n) => (
        <span
          key={n.node}
          className={
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 " +
            (n.status === "done"
              ? "bg-green-100 text-green-700"
              : n.status === "error"
                ? "bg-red-100 text-red-700"
                : "bg-indigo-100 text-indigo-700")
          }
        >
          {n.status === "done" ? "✓" : n.status === "error" ? "✗" : "⏳"}
          {n.label}
        </span>
      ))}
    </div>
  );
}
