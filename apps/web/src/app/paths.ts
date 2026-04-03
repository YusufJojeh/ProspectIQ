export const appPaths = {
  home: "/",
  login: "/login",
  dashboard: "/app",
  searches: "/app/searches",
  leads: "/app/leads",
  settings: "/app/settings",
  leadDetail: (leadId: string) => `/app/leads/${leadId}`,
} as const;

