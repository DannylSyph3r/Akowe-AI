import apiClient from "./client";
import { normalizePhone } from "@/lib/utils";
import type {
  AuthTokens,
  StoredUser,
  StepUpAction,
  StepUpResponse,
} from "./types";

// Storage helpers

export function storeAuthData(tokens: AuthTokens): void {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
  localStorage.setItem(
    "user",
    JSON.stringify({
      id: tokens.member_id,
      full_name: tokens.full_name,
      phone_number: tokens.phone_number,
    } satisfies StoredUser),
  );
}

export function clearAuthStorage(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
  localStorage.removeItem("active_coop_id");
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

// API calls

export async function login(
  phoneNumber: string,
  pin: string,
): Promise<AuthTokens> {
  const response = await apiClient.post("/api/auth/login", {
    phone_number: normalizePhone(phoneNumber),
    pin,
  });
  const tokens = response.data as AuthTokens;
  storeAuthData(tokens);
  return tokens;
}

export async function register(
  fullName: string,
  phoneNumber: string,
  pin: string,
): Promise<AuthTokens> {
  const response = await apiClient.post("/api/auth/register", {
    full_name: fullName,
    phone_number: normalizePhone(phoneNumber),
    pin,
  });
  const tokens = response.data as AuthTokens;
  storeAuthData(tokens);
  return tokens;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/api/auth/logout");
  } finally {
    // Always clear local storage even if the API call fails
    clearAuthStorage();
  }
}

export async function getStepUpToken(
  pin: string,
  action: StepUpAction,
): Promise<string> {
  const response = await apiClient.post("/api/auth/step-up", { pin, action });
  const data = response.data as StepUpResponse;
  return data.step_up_token;
}
