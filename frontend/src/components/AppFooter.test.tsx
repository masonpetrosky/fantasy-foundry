import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("../NewsletterSignup", () => ({
  NewsletterSignup: ({ apiBase }: { apiBase: string }) =>
    React.createElement("div", { "data-testid": "newsletter", "data-api": apiBase }, "Newsletter"),
}));

import { AppFooter } from "./AppFooter";

function renderToContainer(element: React.ReactElement): { container: HTMLDivElement; cleanup: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(element);
  });
  return {
    container,
    cleanup: () => {
      act(() => root.unmount());
      document.body.removeChild(container);
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppFooter", () => {
  it("renders footer element", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={null} buildLabel="" apiBase="http://test" />
    );
    expect(container.querySelector("footer")).not.toBeNull();
    cleanup();
  });

  it("shows default projection update text when no meta", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={null} buildLabel="" apiBase="http://test" />
    );
    expect(container.textContent).toContain("Projections updated as-needed.");
    cleanup();
  });

  it("shows projection update date from meta", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={{ last_projection_update: "March 2026" }} buildLabel="" apiBase="http://test" />
    );
    expect(container.textContent).toContain("Projections updated March 2026.");
    cleanup();
  });

  it("renders build label when provided", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={null} buildLabel="abc123" apiBase="http://test" />
    );
    expect(container.textContent).toContain("Build abc123");
    cleanup();
  });

  it("does not render build label when empty", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={null} buildLabel="" apiBase="http://test" />
    );
    expect(container.querySelector(".build-id")).toBeNull();
    cleanup();
  });

  it("renders NewsletterSignup component", () => {
    const { container, cleanup } = renderToContainer(
      <AppFooter meta={null} buildLabel="" apiBase="http://test-api" />
    );
    expect(container.querySelector("[data-testid='newsletter']")).not.toBeNull();
    cleanup();
  });
});
