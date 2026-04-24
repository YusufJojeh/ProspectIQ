import { request } from "@/lib/api-client";
import type {
  BillingSimulationRequest,
  InvoiceListResponse,
  InvoiceResponse,
  PlanListResponse,
  SubscriptionChangeRequest,
  SubscriptionResponse,
  UsageSummaryResponse,
} from "@/types/api";

export function listPlans() {
  return request<PlanListResponse>("/api/v1/billing/plans");
}

export function getSubscription() {
  return request<SubscriptionResponse>("/api/v1/billing/subscription");
}

export function listInvoices() {
  return request<InvoiceListResponse>("/api/v1/billing/invoices");
}

export function getUsageSummary() {
  return request<UsageSummaryResponse>("/api/v1/billing/usage");
}

export function changeSubscription(payload: SubscriptionChangeRequest) {
  return request<SubscriptionResponse>("/api/v1/billing/subscription/change", { method: "POST" }, payload);
}

export function cancelSubscription() {
  return request<SubscriptionResponse>("/api/v1/billing/subscription/cancel", { method: "POST" });
}

export function renewSubscription() {
  return request<SubscriptionResponse>("/api/v1/billing/subscription/renew", { method: "POST" });
}

export function markInvoicePaid(payload: BillingSimulationRequest) {
  return request<InvoiceResponse>("/api/v1/billing/invoices/mark-paid", { method: "POST" }, payload);
}

export function simulateInvoiceFailure(payload: BillingSimulationRequest) {
  return request<InvoiceResponse>("/api/v1/billing/invoices/simulate-failure", { method: "POST" }, payload);
}
