import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

type FakeSession = {
  public_id: string;
  lead_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
};

type FakeMessage = {
  public_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

/**
 * Builds an in-memory assistant backend for Part 9 (resumable chat history).
 * Routes registered here take precedence over the catch-all in installMockApi.
 */
async function installAssistantHistoryMocks(
  page: import("@playwright/test").Page,
) {
  const sessions = new Map<string, FakeSession>();
  const messagesBySession = new Map<string, FakeMessage[]>();
  let counter = 0;
  const nextId = (prefix: string) =>
    `${prefix}_${++counter}_${Date.now().toString(36)}`;
  const now = () => new Date().toISOString();

  // Helper: build the Vercel AI SDK UI-message-stream SSE response body.
  function buildUiMessageStream(replyText: string): string {
    const messageId = `msg_${nextId("m")}`;
    const textId = `text_${nextId("t")}`;
    const lines: string[] = [];
    const emit = (obj: unknown) =>
      lines.push(`data: ${JSON.stringify(obj)}\n\n`);
    emit({ type: "start", messageId });
    emit({ type: "text-start", id: textId });
    emit({
      type: "data-search",
      id: `search_${nextId("s")}`,
      data: { used_search: false, search_status: "not_needed", sources: [] },
    });
    emit({ type: "text-delta", id: textId, delta: replyText });
    emit({ type: "text-end", id: textId });
    emit({ type: "finish" });
    lines.push("data: [DONE]\n\n");
    return lines.join("");
  }

  await page.route("**/api/v1/assistant/chat", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.fallback();
      return;
    }
    const body = JSON.parse(request.postData() ?? "{}") as {
      messages?: Array<{
        role: string;
        parts?: Array<{ type: string; text?: string }>;
      }>;
      lead_id?: string;
      session_id?: string;
    };
    const latestUserMessage = (body.messages ?? [])
      .filter((m) => m.role === "user")
      .pop();
    const userText =
      (latestUserMessage?.parts ?? [])
        .filter((p) => p.type === "text")
        .map((p) => p.text ?? "")
        .join("\n")
        .trim() || "Untitled question";

    // Resolve session — reuse or create.
    let sessionId = body.session_id;
    if (sessionId && !sessions.has(sessionId)) {
      sessionId = undefined;
    }
    if (!sessionId) {
      sessionId = nextId("cs");
      sessions.set(sessionId, {
        public_id: sessionId,
        lead_id: body.lead_id ?? null,
        title: userText.slice(0, 80),
        created_at: now(),
        updated_at: now(),
        message_count: 0,
        last_message_preview: null,
      });
      messagesBySession.set(sessionId, []);
    }

    const replyText = `E2E assistant reply for: ${userText}`;

    // Persist messages (user + assistant)
    const msgs = messagesBySession.get(sessionId)!;
    msgs.push({
      public_id: nextId("cm"),
      role: "user",
      content: userText,
      created_at: now(),
    });
    msgs.push({
      public_id: nextId("cm"),
      role: "assistant",
      content: replyText,
      created_at: now(),
    });
    const session = sessions.get(sessionId)!;
    session.message_count = msgs.length;
    session.last_message_preview = replyText.slice(0, 120);
    session.updated_at = now();

    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "x-vercel-ai-ui-message-stream": "v1",
      },
      body: buildUiMessageStream(replyText),
    });
  });

  await page.route("**/api/v1/assistant/sessions**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    // Detail route /sessions/<id> handled by separate matcher; only handle list here
    if (/\/api\/v1\/assistant\/sessions\/[^?#]+/.test(url.pathname)) {
      await route.fallback();
      return;
    }
    if (request.method() === "GET") {
      const leadFilter = url.searchParams.get("lead_id");
      const items = Array.from(sessions.values())
        .filter((s) => (leadFilter ? s.lead_id === leadFilter : true))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items }),
      });
      return;
    }
    await route.fallback();
  });

  await page.route(/\/api\/v1\/assistant\/sessions\/[^?#]+/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const match = url.pathname.match(
      /\/api\/v1\/assistant\/sessions\/([^/?#]+)/,
    );
    const sessionId = match?.[1];
    if (!sessionId) {
      await route.fallback();
      return;
    }
    if (request.method() === "GET") {
      const session = sessions.get(sessionId);
      if (!session) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ error: { detail: "Session not found" } }),
        });
        return;
      }
      const messages = messagesBySession.get(sessionId) ?? [];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...session, messages }),
      });
      return;
    }
    if (request.method() === "DELETE") {
      sessions.delete(sessionId);
      messagesBySession.delete(sessionId);
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fallback();
  });
}

test("assistant: user can send a message and resume the conversation from history", async ({
  page,
}) => {
  await installAssistantHistoryMocks(page);
  await gotoPath(page, routes.assistant);

  await expect(
    page.getByRole("heading", { name: /Lead-aware conversational workspace/i }),
  ).toBeVisible();

  // Send the first message (use the prompt textarea)
  const textarea = page.locator("textarea").first();
  await textarea.fill("What is the latest score driver?");
  // Submit via the prompt input submit button (chevron / send icon)
  await textarea.press("Enter");

  // The assistant reply should appear in the conversation
  await expect(
    page.getByText(
      /E2E assistant reply for: What is the latest score driver\?/i,
    ),
  ).toBeVisible({ timeout: 10_000 });

  // Open the history sheet
  await page.getByRole("button", { name: /History/i }).click();

  // The session should appear in the list with the right preview
  const historyDialog = page.getByRole("dialog");
  await expect(historyDialog).toBeVisible();
  // Title span (truncated) shows the session title we created
  await expect(
    historyDialog.getByText(/What is the latest score driver/i).first(),
  ).toBeVisible();
  // Preview shows the assistant reply
  await expect(
    historyDialog.getByText(/E2E assistant reply for/i).first(),
  ).toBeVisible();

  // Click "New chat" to clear, then resume from history
  await historyDialog.getByRole("button", { name: /New chat/i }).click();
  // After "New chat", the conversation should be empty
  await expect(page.getByText(/E2E assistant reply for/i)).toBeHidden();

  // Re-open history and click on the previous session to resume
  await page.getByRole("button", { name: /History/i }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: /Resume/i })
    .first()
    .click();

  // Messages should reappear in the conversation pane (scoped to <main>).
  // Both the user message and the echoed assistant reply contain the question
  // text, so use .first()/.last() to disambiguate.
  const main = page.locator("main");
  await expect(
    main.getByText(/What is the latest score driver/i).first(),
  ).toBeVisible();
  await expect(
    main
      .getByText(/E2E assistant reply for: What is the latest score driver\?/i)
      .first(),
  ).toBeVisible();
});

test("assistant: deleting a chat session removes it from the history list", async ({
  page,
}) => {
  await installAssistantHistoryMocks(page);
  await gotoPath(page, routes.assistant);

  // Seed a session by sending a message
  const textarea = page.locator("textarea").first();
  await textarea.fill("Question to be deleted");
  await textarea.press("Enter");
  await expect(
    page.getByText(/E2E assistant reply for: Question to be deleted/i),
  ).toBeVisible({ timeout: 10_000 });

  // Open history
  await page.getByRole("button", { name: /History/i }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText(/Question to be deleted/i).first(),
  ).toBeVisible();

  // Click the delete (trash) icon — Button with aria-label "Delete chat"
  await dialog
    .getByRole("button", { name: /Delete chat/i })
    .first()
    .click();

  // Confirm in the AlertDialog
  const confirmDialog = page.getByRole("alertdialog");
  await expect(confirmDialog).toBeVisible();
  await confirmDialog.getByRole("button", { name: /Delete chat/i }).click();

  // The session should disappear; empty state appears
  await expect(dialog.getByText(/No previous chats/i)).toBeVisible({
    timeout: 5_000,
  });
});
