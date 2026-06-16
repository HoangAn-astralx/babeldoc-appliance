"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  fetchBlobUrl,
  getJob,
  listArtifacts,
  type Job,
} from "@/lib/api";
import ProgressTracker from "@/components/ProgressTracker";
import PdfViewer from "@/components/PdfViewer";

type BlobMap = Record<string, string>;

export default function JobPage({ params }: { params: { id: string } }) {
  const jobId = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [artifacts, setArtifacts] = useState<string[]>([]);
  const [blobs, setBlobs] = useState<BlobMap>({});
  const [loadingBlobs, setLoadingBlobs] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"dual" | "compare">("dual");
  const blobsRef = useRef<BlobMap>({});

  // Revoke blob URLs on unmount to avoid memory leaks.
  useEffect(() => {
    return () => {
      Object.values(blobsRef.current).forEach(URL.revokeObjectURL);
    };
  }, []);

  async function loadBlob(name: string) {
    if (blobsRef.current[name]) return;
    setLoadingBlobs((p) => ({ ...p, [name]: true }));
    try {
      const url = await fetchBlobUrl(jobId, name);
      blobsRef.current[name] = url;
      setBlobs((p) => ({ ...p, [name]: url }));
    } catch {
      /* silent — viewer shows "Không có dữ liệu" */
    } finally {
      setLoadingBlobs((p) => ({ ...p, [name]: false }));
    }
  }

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const j = await getJob(jobId);
        if (!active) return;
        setJob(j);
        if (j.status === "done") {
          const a = await listArtifacts(jobId);
          if (!active) return;
          setArtifacts(a.artifacts);
          // Start loading the default view's blob immediately.
          if (a.artifacts.includes("dual")) loadBlob("dual");
          return;
        }
        if (j.status === "failed") return;
        timer = setTimeout(poll, 1500);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Lỗi tải job");
      }
    }
    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  // Load blobs when switching views.
  useEffect(() => {
    if (artifacts.length === 0) return;
    if (view === "dual") {
      if (artifacts.includes("dual")) loadBlob("dual");
    } else {
      if (artifacts.includes("source")) loadBlob("source");
      if (artifacts.includes("mono")) loadBlob("mono");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, artifacts]);

  if (error)
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">{error}</p>;
  if (!job) return <p className="text-gray-500">Đang tải...</p>;

  const done = job.status === "done";
  const sourceName = job.source_file_name || "document.pdf";

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col gap-4 overflow-hidden">
      {/* Top bar */}
      <div className="flex shrink-0 items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900 truncate max-w-md">
            {sourceName}
          </h1>
          <p className="text-sm text-gray-500">
            {job.target_language} · {job.model}
          </p>
        </div>
        <div className="flex items-center gap-3">
        </div>
      </div>

      {/* Progress while running */}
      {!done && (
        <div className="shrink-0">
          <ProgressTracker job={job} />
        </div>
      )}

      {/* Result viewer */}
      {done && (
        <>
          {/* View toggle */}
          <div className="shrink-0 inline-flex rounded-lg border bg-white p-1 text-sm">
            <button
              onClick={() => setView("dual")}
              className={`rounded-md px-4 py-1.5 transition-colors ${
                view === "dual"
                  ? "bg-brand-600 text-white"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Song ngữ
            </button>
            <button
              onClick={() => setView("compare")}
              className={`rounded-md px-4 py-1.5 transition-colors ${
                view === "compare"
                  ? "bg-brand-600 text-white"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              So sánh gốc / dịch
            </button>
          </div>

          {/* Viewers */}
          <div className="min-h-0 flex-1 overflow-hidden">
            {view === "dual" ? (
              <PdfViewer
                blobUrl={blobs["dual"] ?? null}
                loading={loadingBlobs["dual"]}
                title="Bản song ngữ"
                downloadName={sourceName.replace(/\.pdf$/i, ".dual.pdf")}
                accent="brand"
              />
            ) : (
              <div className="grid h-full gap-4 md:grid-cols-2">
                <PdfViewer
                  blobUrl={blobs["source"] ?? null}
                  loading={loadingBlobs["source"]}
                  title="Bản gốc"
                  downloadName={sourceName}
                  accent="slate"
                />
                <PdfViewer
                  blobUrl={blobs["mono"] ?? null}
                  loading={loadingBlobs["mono"]}
                  title="Bản dịch"
                  downloadName={sourceName.replace(/\.pdf$/i, ".vi.pdf")}
                  accent="brand"
                />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
