"use client";

import type { Job } from "@/lib/api";

const STAGES: { key: string; label: string }[] = [
  { key: "analyze", label: "Phân tích bố cục" },
  { key: "translate", label: "Dịch nội dung" },
  { key: "render", label: "Dựng lại PDF" },
];

export default function ProgressTracker({ job }: { job: Job }) {
  const pct = Math.round(job.progress ?? 0);
  const currentIndex = STAGES.findIndex((s) => s.key === job.stage);
  const failed = job.status === "failed";

  return (
    <div className="rounded-xl border bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold text-gray-800">
          {failed
            ? "Dịch thất bại"
            : job.status === "done"
              ? "Hoàn tất"
              : "Đang xử lý..."}
        </h2>
        <span className="text-sm text-gray-500">{pct}%</span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            failed ? "bg-red-500" : "bg-brand-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="mt-5 space-y-2">
        {STAGES.map((stage, i) => {
          const done = job.status === "done" || (currentIndex > -1 && i < currentIndex);
          const active = currentIndex === i && job.status === "running";
          return (
            <li key={stage.key} className="flex items-center gap-3 text-sm">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                  done
                    ? "bg-brand-600 text-white"
                    : active
                      ? "bg-brand-100 text-brand-700 ring-2 ring-brand-400"
                      : "bg-gray-100 text-gray-400"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span className={active ? "font-medium text-gray-800" : "text-gray-500"}>
                {stage.label}
                {active && " …"}
              </span>
            </li>
          );
        })}
      </ol>

      {failed && job.error && (
        <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {job.error}
        </p>
      )}
    </div>
  );
}
