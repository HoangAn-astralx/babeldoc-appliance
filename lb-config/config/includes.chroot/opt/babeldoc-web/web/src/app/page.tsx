"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import UploadZone from "@/components/UploadZone";
import { createJob, listModels, uploadFile } from "@/lib/api";

const LANGUAGES = [
  { code: "vi", label: "Tiếng Việt" },
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "fr", label: "Français" },
];

export default function HomePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [targetLang, setTargetLang] = useState("vi");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [splitShortLines, setSplitShortLines] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listModels()
      .then((res) => {
        setModels(res.models);
        setModel(res.default);
      })
      .catch(() => setModels([]));
  }, []);

  async function handleSubmit() {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    try {
      const { upload_id } = await uploadFile(file);
      const job = await createJob({
        upload_id,
        target_language: targetLang,
        model: model || undefined,
        split_short_lines: splitShortLines,
      });
      router.push(`/jobs/${job.job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Đã xảy ra lỗi");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dịch PDF giữ nguyên bố cục</h1>
        <p className="mt-1 text-gray-500">
          Tải lên file PDF, BabelDOC sẽ dịch và dựng lại tài liệu giữ nguyên layout, công thức và hình ảnh.
        </p>
      </div>

      <UploadZone file={file} onFile={setFile} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Ngôn ngữ đích
          </label>
          <select
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Mô hình LLM
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            {models.length === 0 && <option value="">(mặc định)</option>}
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Advanced option */}
      <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-200 bg-white p-3 hover:border-brand-400 transition-colors">
        <input
          type="checkbox"
          checked={splitShortLines}
          onChange={(e) => setSplitShortLines(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
        />
        <div>
          <p className="text-sm font-medium text-gray-800">Giữ nguyên từng dòng ngắn</p>
          <p className="text-xs text-gray-500 mt-0.5">
            Dùng cho memo, form, bảng biểu — ngăn BabelDOC gộp các dòng ngắn thành đoạn văn rồi mất xuống dòng
          </p>
        </div>
      </label>

      {error && (
        <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      <button
        onClick={handleSubmit}
        disabled={!file || submitting}
        className="w-full rounded-lg bg-brand-600 px-4 py-3 font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {submitting ? "Đang gửi..." : "Bắt đầu dịch"}
      </button>
    </div>
  );
}
