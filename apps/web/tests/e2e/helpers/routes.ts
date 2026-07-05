import { MOCK_IDS } from "../support/mock-api";

export const routes = {
  home: "/",
  login: "/login",
  signUp: "/sign-up",
  forgotPassword: "/forgot-password",
  dashboard: "/app",
  searches: "/app/searches",
  leads: "/app/leads",
  leadDetail: `/app/leads/${MOCK_IDS.primaryLeadId}`,
  aiAnalysis: "/app/ai-analysis",
  assistant: "/app/assistant",
  outreach: "/app/outreach",
  // Workspace-level admin dashboard (RequireRole: account_owner/admin).
  // Not to be confused with `/app/admin`, which is the separate
  // platform_admin-only entry point (see AdminEntryPage in router.tsx).
  admin: "/app/workspace-admin",
  platformAdmin: "/app/admin",
  auditLogs: "/app/audit-logs",
  exports: "/app/exports",
  settings: "/app/settings",
  team: "/app/team",
  billing: "/app/billing",
  invoices: "/app/invoices",
  usage: "/app/usage",
  searchJobLeads: `/app/leads?search_job_id=${MOCK_IDS.seedJobId}`,
} as const;
