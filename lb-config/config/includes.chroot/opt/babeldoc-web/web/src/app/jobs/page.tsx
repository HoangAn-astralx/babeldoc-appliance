"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteJob, listJobs, type Job } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  pending: "Chờ xử lý",
  running: "Đang chạy",
  done: "Hoàn tất",
  failed: "Thất bại",
  cancelled: "Đã hủy",
};

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const res = await listJobs();
    setJobs(res.jobs);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Xóa job này?")) return;
    await deleteJob(id);
    refresh();
  }

  if (loading) return <p className="text-gray-500">Đang tải...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-900">Lịch sử dịch</h1>
      {jobs.length === 0 ? (
        <p className="text-gray-500">Chưa có job nào.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Tài liệu</th>
                <th className="px-4 py-2 font-medium">Ngôn ngữ</th>
                <th className="px-4 py-2 font-medium">Trạng thái</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.job_id} className="border-b last:border-0">
                  <td className="px-4 py-2">
                    <Link
                      href={`/jobs/${j.job_id}`}
                      className="text-brand-600 hover:text-brand-700"
                    >
                      {j.source_file_name || j.job_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-gray-600">{j.target_language}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        STATUS_STYLE[j.status] || "bg-gray-100"
                      }`}
                    >
                      {STATUS_LABEL[j.status] || j.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleDelete(j.job_id)}
                      className="text-xs text-gray-400 hover:text-red-600"
                    >
                      Xóa
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
