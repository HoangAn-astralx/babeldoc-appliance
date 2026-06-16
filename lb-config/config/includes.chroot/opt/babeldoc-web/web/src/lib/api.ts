const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export type JobStatus = "pending" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  job_id: string;
  status: JobStatus;
  stage?: string | null;
  progress?: number | null;
  source_file_name?: string | null;
  target_language?: string | null;
  model?: string | null;
  error?: string | null;
}

export interface CreateJobParams {
  upload_id: string;
  target_language?: string;
  model?: string;
  split_short_lines?: boolean;
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function uploadFile(file: File): Promise<{ upload_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/v1/uploads", {
    method: "POST",
    headers: headers(),
    body: form,
  });
  return asJson(res);
}

export async function createJob(params: CreateJobParams): Promise<Job> {
  const res = await fetch("/api/v1/jobs", {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(params),
  });
  return asJson(res);
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`/api/v1/jobs/${jobId}`, { headers: headers() });
  return asJson(res);
}

export async function listJobs(limit = 50): Promise<{ jobs: Job[] }> {
  const res = await fetch(`/api/v1/jobs?limit=${limit}`, { headers: headers() });
  return asJson(res);
}

export async function deleteJob(jobId: string): Promise<void> {
  await fetch(`/api/v1/jobs/${jobId}`, { method: "DELETE", headers: headers() });
}

export async function rerunJob(
  jobId: string,
  opts: { ignore_cache?: boolean; model?: string } = {}
): Promise<Job> {
  const res = await fetch(`/api/v1/jobs/${jobId}/rerun`, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify({ ignore_cache: opts.ignore_cache ?? true, model: opts.model }),
  });
  return asJson(res);
}

export async function listArtifacts(
  jobId: string
): Promise<{ artifacts: string[] }> {
  const res = await fetch(`/api/v1/jobs/${jobId}/artifacts`, {
    headers: headers(),
  });
  return asJson(res);
}

export function artifactUrl(jobId: string, name: string): string {
  const key = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  return `/api/v1/jobs/${jobId}/artifacts/${name}${key}`;
}

export async function fetchBlobUrl(jobId: string, name: string): Promise<string> {
  const res = await fetch(`/api/v1/jobs/${jobId}/artifacts/${name}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to fetch artifact: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function listModels(): Promise<{
  default: string;
  models: string[];
}> {
  const res = await fetch("/api/v1/models", { headers: headers() });
  return asJson(res);
}
