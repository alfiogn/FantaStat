import type { ForecastRequest, ForecastResponse } from "./types";
export async function runSeasonForecast(baseUrl: string, player: string, year: number, request: ForecastRequest): Promise<ForecastResponse> {
  const response = await fetch(`${baseUrl}/api/v1/players/${encodeURIComponent(player)}/seasons/${year}/forecast`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
  if (!response.ok) throw new Error((await response.json()).detail ?? `HTTP ${response.status}`);
  return response.json();
}
