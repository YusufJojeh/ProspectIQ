import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QueryStateNotice } from "@/components/shared/query-state-notice";

describe("QueryStateNotice", () => {
  it("renders an accessible loading state", () => {
    render(
      <QueryStateNotice
        tone="loading"
        title="Loading workspace snapshot"
        description="Fetching lead coverage from the API."
      />,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading workspace snapshot")).toBeInTheDocument();
    expect(screen.getByText("Fetching lead coverage from the API.")).toBeInTheDocument();
  });

  it("renders an alert role for errors", () => {
    render(
      <QueryStateNotice
        tone="error"
        title="Run queue is unavailable"
        description="The API returned an error."
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("The API returned an error.")).toBeInTheDocument();
  });
});
