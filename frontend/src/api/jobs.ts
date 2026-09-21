import type { DiagnosticJobView, FormatJobResult } from "../types/diagnosis";

interface ApiErrorBody {
  detail?: { code?: string; message?: string; job_id?: string | null } | string;
}

export class DiagnosticApiError extends Error {
  readonly code: string;
  readonly jobId: string | null;

  constructor(message: string, code = "request_failed", jobId: string | null = null) {
    super(message);
    this.name = "DiagnosticApiError";
    this.code = code;
    this.jobId = jobId;
  }
}

async function parseResponse(response: Response): Promise<DiagnosticJobView> {
  if (response.ok) return (await response.json()) as DiagnosticJobView;
  let body: ApiErrorBody = {};
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    throw new DiagnosticApiError(`请求失败（${response.status}）`);
  }
  if (typeof body.detail === "object" && body.detail) {
    throw new DiagnosticApiError(
      body.detail.message ?? `请求失败（${response.status}）`,
      body.detail.code,
      body.detail.job_id ?? null,
    );
  }
  throw new DiagnosticApiError(
    typeof body.detail === "string" ? body.detail : `请求失败（${response.status}）`,
  );
}

export async function createDiagnosticJob(file: File): Promise<DiagnosticJobView> {
  const response = await fetch(`/api/jobs?filename=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: { "content-type": file.type || "application/octet-stream" },
    body: file,
  });
  return parseResponse(response);
}

export async function getDiagnosticJob(jobId: string): Promise<DiagnosticJobView> {
  return parseResponse(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`));
}

export async function formatDiagnosticJob(
  jobId: string,
  approvedRuleIds: string[],
): Promise<FormatJobResult> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/format`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ approved_rule_ids: approvedRuleIds }),
  });
  if (!response.ok) {
    await parseResponse(response);
    throw new DiagnosticApiError("排版请求失败。");
  }
  return (await response.json()) as FormatJobResult;
}

export function formattedDownloadUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/download`;
}
