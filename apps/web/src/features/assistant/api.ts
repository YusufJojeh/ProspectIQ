import { DefaultChatTransport, type UIMessage } from "ai";
import { buildRequestUrl, readToken } from "@/lib/api-client";

export interface AssistantChatRequestBody {
  lead_id?: string;
  mode?: "lead-assistant";
}

export function createAssistantTransport(body?: AssistantChatRequestBody) {
  return new DefaultChatTransport<UIMessage>({
    api: buildRequestUrl("/api/v1/assistant/chat"),
    body,
    headers: readToken() ? { Authorization: `Bearer ${readToken()}` } : undefined,
  });
}
