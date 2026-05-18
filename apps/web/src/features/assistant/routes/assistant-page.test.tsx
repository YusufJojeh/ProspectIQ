import { cleanup, render, screen } from "@testing-library/react";
import type { UIMessage } from "ai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantSearchEvidence } from "@/features/assistant/routes/assistant-page";

vi.mock("react-i18next", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-i18next")>();
  return {
    ...actual,
    useTranslation: () => ({
      t: (key: string) => {
        const map: Record<string, string> = {
          "assistant.sources": "المصادر",
          "assistant.searchUsed": "تم استخدام البحث",
          "assistant.searchUnavailable": "البحث الخارجي غير متاح",
          "assistant.searchFailed": "فشل البحث الخارجي",
          "assistant.externalEvidence": "أدلة خارجية",
          "assistant.basedOnSystemData": "بناءً على بيانات النظام",
        };
        return map[key] ?? key;
      },
      i18n: { changeLanguage: vi.fn() },
    }),
  };
});

function assistantMessage(data: unknown): UIMessage {
  return {
    id: "msg_1",
    role: "assistant",
    parts: [{ type: "data-search", data }],
  } as unknown as UIMessage;
}

describe("AssistantSearchEvidence", () => {
  afterEach(() => cleanup());

  it("renders compact sources when assistant search evidence is present", () => {
    render(
      <AssistantSearchEvidence
        message={assistantMessage({
          used_search: true,
          search_status: "used",
          sources: [
            {
              title: "Acme Dental",
              url: "https://acmedental.example",
              snippet: "Official website result.",
              provider: "serpapi",
            },
          ],
        })}
      />,
    );

    expect(screen.getByText("تم استخدام البحث")).toBeInTheDocument();
    expect(screen.getByText("أدلة خارجية")).toBeInTheDocument();
    expect(screen.getByText("المصادر")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Acme Dental/i })).toHaveAttribute(
      "href",
      "https://acmedental.example",
    );
    expect(screen.getByText("Official website result.")).toBeInTheDocument();
  });

  it("does not render an empty source box when search was not needed", () => {
    const { container } = render(
      <AssistantSearchEvidence
        message={assistantMessage({
          used_search: false,
          search_status: "not_needed",
          sources: [],
        })}
      />,
    );

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("المصادر")).not.toBeInTheDocument();
  });

  it("renders Arabic unavailable status without exposing sources", () => {
    render(
      <AssistantSearchEvidence
        message={assistantMessage({
          used_search: false,
          search_status: "unavailable",
          sources: [],
        })}
      />,
    );

    expect(screen.getByText("البحث الخارجي غير متاح")).toBeInTheDocument();
    expect(screen.queryByText("المصادر")).not.toBeInTheDocument();
  });
});
