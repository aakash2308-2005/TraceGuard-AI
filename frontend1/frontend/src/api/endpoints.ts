// Typed API wrappers for all backend endpoints.
import { api } from "./client";
import type {
  AuditEvent,
  CaseItem,
  Confidence,
  Contradiction,
  Evidence,
  Finding,
  GraphData,
  InvestigationStatus,
  Me,
  Member,
  Report,
  TimelineEvent,
  UserItem,
} from "./types";

// --- Auth ---
export async function login(username: string, password: string) {
  const res = await api.post<{ access_token: string; refresh_token: string }>("/auth/login", {
    username,
    password,
  });
  return res.data;
}

export async function getMe() {
  const res = await api.get<Me>("/auth/me");
  return res.data;
}

// --- Cases ---
export async function listCases() {
  const res = await api.get<CaseItem[]>("/cases");
  return res.data;
}

export async function getCase(caseId: string) {
  const res = await api.get<CaseItem>(`/cases/${caseId}`);
  return res.data;
}

export async function closeCase(caseId: string) {
  const res = await api.patch<CaseItem>(`/cases/${caseId}`, { status: "closed" });
  return res.data;
}

export async function createCase(
  caseIdentifier: string,
  title: string,
  description: string,
  caseRole: string,
) {
  const res = await api.post<CaseItem>("/cases", {
    case_identifier: caseIdentifier,
    title,
    description,
    case_role: caseRole,
  });
  return res.data;
}

export async function listMembers(caseId: string) {
  const res = await api.get<Member[]>(`/cases/${caseId}/members`);
  return res.data;
}

// --- Evidence ---
export async function listEvidence(caseId: string) {
  const res = await api.get<Evidence[]>(`/cases/${caseId}/evidence`);
  return res.data;
}

export async function submitIndicator(
  caseId: string,
  indicatorType: string,
  value: string,
  source?: string,
) {
  const res = await api.post<Evidence>(`/cases/${caseId}/evidence/indicator`, {
    indicator_type: indicatorType,
    value,
    source,
  });
  return res.data;
}

export async function uploadFile(caseId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<Evidence>(`/cases/${caseId}/evidence`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function verifyEvidence(caseId: string, evidenceId: string) {
  const res = await api.post(`/cases/${caseId}/evidence/${evidenceId}/verify`);
  return res.data;
}

// --- Investigations ---
export async function startInvestigation(caseId: string) {
  const res = await api.post<{ id: string; case_id: string; status: string }>(
    `/cases/${caseId}/investigations`,
  );
  return res.data;
}

export async function getInvestigation(id: string) {
  const res = await api.get<InvestigationStatus>(`/investigations/${id}`);
  return res.data;
}

export async function cancelInvestigation(id: string) {
  const res = await api.post(`/investigations/${id}/cancel`);
  return res.data;
}

export async function getFindings(id: string) {
  const res = await api.get<Finding[]>(`/investigations/${id}/findings`);
  return res.data;
}

export async function getContradictions(id: string) {
  const res = await api.get<Contradiction[]>(`/investigations/${id}/contradictions`);
  return res.data;
}

export async function getConfidence(id: string) {
  const res = await api.get<Confidence>(`/investigations/${id}/confidence`);
  return res.data;
}

export async function getInvestigationTimeline(id: string) {
  const res = await api.get<{ events: TimelineEvent[] }>(`/investigations/${id}/timeline`);
  return res.data.events;
}

// --- Graph & timeline (case-scoped) ---
export async function getGraph(caseId: string) {
  const res = await api.get<GraphData>(`/cases/${caseId}/graph`);
  return res.data;
}

export async function getCaseTimeline(caseId: string) {
  const res = await api.get<{ events: TimelineEvent[] }>(`/cases/${caseId}/timeline`);
  return res.data.events;
}

// --- Reports ---
export async function generateReport(investigationId: string) {
  const res = await api.post<Report>(`/investigations/${investigationId}/report`);
  return res.data;
}

export async function getReport(reportId: string) {
  const res = await api.get<Report>(`/reports/${reportId}`);
  return res.data;
}

export async function approveReport(reportId: string) {
  const res = await api.post<Report>(`/reports/${reportId}/approve`);
  return res.data;
}

// --- Audit ---
export async function getCaseAudit(caseId: string) {
  const res = await api.get<AuditEvent[]>(`/cases/${caseId}/audit`);
  return res.data;
}

// --- Admin ---
export async function listUsers() {
  const res = await api.get<UserItem[]>("/admin/users");
  return res.data;
}

export async function createUser(
  username: string,
  email: string,
  password: string,
  role: string,
) {
  const res = await api.post<UserItem>("/admin/users", { username, email, password, role });
  return res.data;
}

export async function getConfig() {
  const res = await api.get<Record<string, unknown>>("/admin/config");
  return res.data;
}
