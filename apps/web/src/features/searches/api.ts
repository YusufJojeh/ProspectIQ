import { request } from "@/lib/api-client";
import type { SearchJobCreateRequest, SearchJobListResponse, SearchJobResponse } from "@/types/api";

export function createSearchJob(payload: SearchJobCreateRequest) {
  return request<SearchJobResponse>("/api/v1/search-jobs", { method: "POST" }, payload);
}

export function createSearchJobFromPrompt(prompt: string) {
  return request<SearchJobResponse>("/api/v1/search-jobs/from-prompt", { method: "POST" }, { prompt });
}

export function listSearchJobs() {
  return request<SearchJobListResponse>("/api/v1/search-jobs");
}

export function getSearchJob(jobId: string) {
  return request<SearchJobResponse>(`/api/v1/search-jobs/${jobId}`);
}
