export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  stage: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch("/health");
  if (!response.ok) {
    throw new Error(`Health check failed with ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}
