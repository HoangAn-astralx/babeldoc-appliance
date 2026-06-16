"use client";

import React, { useEffect, useRef, useState } from "react";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyComp = React.ComponentType<any>;
interface PdfLib {
  Document: AnyComp;
  Page: AnyComp;
}

let _libCache: PdfLib | null = null;
async function loadPdfLib(): Promise<PdfLib> {
  if (_libCache) return _libCache;
  const mod = await import("react-pdf");
  mod.pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.js",
    import.meta.url,
  ).toString();
  _libCache = { Document: mod.Document, Page: mod.Page };
  return _libCache;
}

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const A4_RATIO = 1.414;

function LazyPage({
  lib,
  pageNumber,
  width,
  scrollRoot,
}: {
  lib: PdfLib;
  pageNumber: number;
  width: number;
  scrollRoot: React.RefObject<HTMLDivElement>;
}) {
  const [visible, setVisible] = useState(pageNumber <= 2);
  const ref = useRef<HTMLDivElement>(null);
  const skeletonH = Math.round(width * A4_RATIO);

  useEffect(() => {
    if (visible) return;
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { root: scrollRoot.current, rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [visible, scrollRoot]);

  return (
    <div
      ref={ref}
      style={{ width }}
      className="shrink-0 overflow-hidden rounded shadow-md"
    >
      {visible ? (
        <lib.Page
          pageNumber={pageNumber}
          width={width}
          renderAnnotationLayer={false}
          renderTextLayer={false}
          loading={
            <div
              className="animate-pulse rounded bg-gray-200"
              style={{ width, height: skeletonH }}
            />
          }
        />
      ) : (
        <div
          className="animate-pulse rounded bg-gray-200"
          style={{ width, height: skeletonH }}
        />
      )}
    </div>
  );
}

export default function PdfViewer({
  blobUrl,
  title,
  loading,
  downloadName,
  accent = "brand",
}: {
  blobUrl: string | null;
  title: string;
  loading?: boolean;
  downloadName?: string;
  accent?: "brand" | "slate";
}) {
  const [lib, setLib] = useState<PdfLib | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [zoomIdx, setZoomIdx] = useState(2);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState(600);

  useEffect(() => {
    loadPdfLib().then(setLib).catch(console.error);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w > 0) setPageWidth(Math.floor(w - 32));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const zoom = ZOOM_STEPS[zoomIdx];
  const safeW = Math.max(300, Math.floor(pageWidth * zoom));
  const dotColor = accent === "brand" ? "bg-brand-500" : "bg-slate-500";
  const btnColor =
    accent === "brand"
      ? "bg-brand-600 hover:bg-brand-700"
      : "bg-slate-700 hover:bg-slate-800";
  const spinColor =
    accent === "brand" ? "text-brand-500" : "text-slate-400";

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
          <span className="text-sm font-semibold text-gray-900">{title}</span>
          {numPages > 0 && (
            <span className="text-xs text-gray-400">· {numPages} trang</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Zoom */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => setZoomIdx((i) => Math.max(0, i - 1))}
              disabled={zoomIdx === 0}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-sm font-bold text-gray-500 hover:bg-gray-100 disabled:opacity-30"
            >
              −
            </button>
            <span className="w-10 text-center text-xs tabular-nums text-gray-500">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() =>
                setZoomIdx((i) => Math.min(ZOOM_STEPS.length - 1, i + 1))
              }
              disabled={zoomIdx === ZOOM_STEPS.length - 1}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-sm font-bold text-gray-500 hover:bg-gray-100 disabled:opacity-30"
            >
              +
            </button>
          </div>
          {blobUrl && (
            <a
              href={blobUrl}
              download={downloadName || "document.pdf"}
              className={`inline-flex items-center gap-1.5 rounded-md ${btnColor} px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors`}
            >
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"
                />
              </svg>
              Tải xuống
            </a>
          )}
        </div>
      </div>

      {/* PDF area */}
      <div ref={containerRef} className="min-h-0 flex-1 overflow-hidden bg-gray-100">
        {blobUrl && lib ? (
          <div
            ref={scrollRef}
            className="flex h-full flex-col items-center gap-3 overflow-auto p-4"
          >
            <lib.Document
              file={blobUrl}
              onLoadSuccess={({ numPages: n }: { numPages: number }) =>
                setNumPages(n)
              }
              loading={<Spinner color={spinColor} />}
              error={
                <p className="py-8 text-center text-sm text-red-600">
                  Không thể tải file PDF
                </p>
              }
            >
              {Array.from({ length: numPages }, (_, i) => (
                <LazyPage
                  key={i + 1}
                  lib={lib}
                  pageNumber={i + 1}
                  width={safeW}
                  scrollRoot={scrollRef}
                />
              ))}
            </lib.Document>
          </div>
        ) : loading || (blobUrl && !lib) ? (
          <div className="flex h-full items-center justify-center">
            <Spinner color={spinColor} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">
            Không có dữ liệu
          </div>
        )}
      </div>
    </div>
  );
}

function Spinner({ color }: { color: string }) {
  return (
    <div className={`flex flex-col items-center gap-3 ${color}`}>
      <svg className="h-10 w-10 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="3"
          className="opacity-20"
        />
        <path
          d="M4 12a8 8 0 018-8"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <p className="text-sm text-gray-400">Đang tải PDF…</p>
    </div>
  );
}
