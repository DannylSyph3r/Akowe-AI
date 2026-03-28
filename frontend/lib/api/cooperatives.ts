import apiClient from "./client";
import type {
  BroadcastResponse,
  ChatResponse,
  ContributionSummaryItem,
  CooperativeDetail,
  CooperativeListItem,
  CreateCoopRequest,
  CreateCoopResponse,
  ExcoInviteResponse,
  GenerateJoinCodesResponse,
  InsightResponse,
  MemberListItem,
  PaginatedWithdrawals,
  PeriodListItem,
  PeriodStatusItem,
  RecordWithdrawalRequest,
  RecordWithdrawalResponse,
  UpdateSettingsRequest,
} from "./types";

export async function listCooperatives(): Promise<CooperativeListItem[]> {
  const r = await apiClient.get("/api/cooperatives");
  return r.data as CooperativeListItem[];
}

export async function getCooperative(
  coopId: string,
): Promise<CooperativeDetail> {
  const r = await apiClient.get(`/api/cooperatives/${coopId}`);
  return r.data as CooperativeDetail;
}

export async function createCooperative(
  data: CreateCoopRequest,
): Promise<CreateCoopResponse> {
  const r = await apiClient.post("/api/cooperatives", data);
  return r.data as CreateCoopResponse;
}

export async function updateSettings(
  coopId: string,
  data: UpdateSettingsRequest,
  stepUpToken: string,
): Promise<CooperativeDetail> {
  const r = await apiClient.patch(
    `/api/cooperatives/${coopId}/settings`,
    data,
    {
      headers: { "X-Step-Up-Token": stepUpToken },
    },
  );
  return r.data as CooperativeDetail;
}

export async function getMembers(coopId: string): Promise<MemberListItem[]> {
  const r = await apiClient.get(`/api/cooperatives/${coopId}/members`);
  return r.data as MemberListItem[];
}

export async function generateJoinCodes(
  coopId: string,
  count: number,
  expiresInDays: number,
): Promise<GenerateJoinCodesResponse> {
  const r = await apiClient.post(`/api/cooperatives/${coopId}/join-codes`, {
    count,
    expires_in_days: expiresInDays,
  });
  return r.data as GenerateJoinCodesResponse;
}

export async function generateExcoInvite(
  coopId: string,
  expiresInDays: number,
): Promise<ExcoInviteResponse> {
  const r = await apiClient.post(`/api/cooperatives/${coopId}/exco-invites`, {
    expires_in_days: expiresInDays,
  });
  return r.data as ExcoInviteResponse;
}

export async function getPeriods(coopId: string): Promise<PeriodListItem[]> {
  const r = await apiClient.get(`/api/cooperatives/${coopId}/periods`);
  return r.data as PeriodListItem[];
}

export async function getContributionsSummary(
  coopId: string,
): Promise<ContributionSummaryItem[]> {
  const r = await apiClient.get(
    `/api/cooperatives/${coopId}/contributions/summary`,
  );
  return r.data as ContributionSummaryItem[];
}

export async function getPeriodStatus(
  coopId: string,
  periodId: string,
): Promise<PeriodStatusItem[]> {
  const r = await apiClient.get(
    `/api/cooperatives/${coopId}/contributions/period-status`,
    { params: { period_id: periodId } },
  );
  return r.data as PeriodStatusItem[];
}

export async function getWithdrawals(
  coopId: string,
  page = 1,
): Promise<PaginatedWithdrawals> {
  const r = await apiClient.get(`/api/cooperatives/${coopId}/withdrawals`, {
    params: { page },
  });
  return r.data as PaginatedWithdrawals;
}

export async function recordWithdrawal(
  coopId: string,
  data: RecordWithdrawalRequest,
  stepUpToken: string,
): Promise<RecordWithdrawalResponse> {
  const r = await apiClient.post(
    `/api/cooperatives/${coopId}/withdrawals`,
    data,
    { headers: { "X-Step-Up-Token": stepUpToken } },
  );
  return r.data as RecordWithdrawalResponse;
}

export async function getInsights(coopId: string): Promise<InsightResponse> {
  const r = await apiClient.get(`/api/cooperatives/${coopId}/insights`);
  return r.data as InsightResponse;
}

export async function broadcastMessage(
  coopId: string,
  message: string,
  stepUpToken: string,
): Promise<BroadcastResponse> {
  const r = await apiClient.post(
    `/api/cooperatives/${coopId}/broadcast`,
    { message },
    { headers: { "X-Step-Up-Token": stepUpToken } },
  );
  return r.data as BroadcastResponse;
}

export async function sendChat(
  coopId: string,
  question: string,
): Promise<ChatResponse> {
  const r = await apiClient.post(`/api/cooperatives/${coopId}/chat`, {
    question,
  });
  return r.data as ChatResponse;
}
