import { DefaultChatTransport, type UIMessage } from "ai";
import { buildRequestUrl, readToken, request } from "@/lib/api-client";

export interface AssistantChatRequestBody {
  lead_id?: string;
  session_id?: string;
  mode?: "lead-assistant";
}

export function createAssistantTransport(body?: AssistantChatRequestBody) {
  return new DefaultChatTransport<UIMessage>({
    api: buildRequestUrl("/api/v1/assistant/chat"),
    body,
    headers: readToken()
      ? { Authorization: `Bearer ${readToken()}` }
      : undefined,
  });
}

// ----- Chat history -----

export type ChatSessionSummary = {
  public_id: string;
  lead_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
};

export type ChatMessageRecord = {
  public_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

export type ChatSessionDetail = ChatSessionSummary & {
  messages: ChatMessageRecord[];
};

type ChatSessionListResponse = {
  items: ChatSessionSummary[];
};

export async function listChatSessions(
  leadId?: string,
): Promise<ChatSessionSummary[]> {
  const query = leadId ? `?lead_id=${encodeURIComponent(leadId)}` : "";
  const response = await request<ChatSessionListResponse>(
    `/api/v1/assistant/sessions${query}`,
    { method: "GET" },
  );
  return response.items;
}

export async function getChatSession(
  sessionId: string,
): Promise<ChatSessionDetail> {
  return request<ChatSessionDetail>(
    `/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}`,
    { method: "GET" },
  );
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await request<null>(
    `/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
}
