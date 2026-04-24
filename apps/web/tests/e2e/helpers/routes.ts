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
  outreach: "/app/outreach",
  admin: "/app/admin",
  auditLogs: "/app/audit-logs",
  exports: "/app/exports",
  settings: "/app/settings",
  team: "/app/team",
  billing: "/app/billing",
  invoices: "/app/invoices",
  usage: "/app/usage",
  searchJobLeads: `/app/leads?search_job_id=${MOCK_IDS.seedJobId}`,
} as const;
