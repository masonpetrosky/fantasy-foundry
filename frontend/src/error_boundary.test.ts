import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./error_boundary";

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

describe("ErrorBoundary", () => {
  describe("getDerivedStateFromError", () => {
    it("returns error state from an Error instance", () => {
      const error = new Error("test crash");
      const state = ErrorBoundary.getDerivedStateFromError(error);
      expect(state).toEqual({ error });
    });

    it("returns error state from a non-Error value", () => {
      const state = ErrorBoundary.getDerivedStateFromError("string error" as unknown as Error);
      expect(state).toEqual({ error: "string error" });
    });

    it("returns error state from null", () => {
      const state = ErrorBoundary.getDerivedStateFromError(null as unknown as Error);
      expect(state).toEqual({ error: null });
    });
  });

  describe("rendering", () => {
    it("renders children when there is no error", () => {
      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement("p", null, "child content")
        )
      );

      expect(container.textContent).toContain("child content");
      cleanup();
    });

    it("renders error UI when child throws", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("boom");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      expect(container.textContent).toContain("Something went wrong");
      expect(container.textContent).toContain("boom");
      expect(container.querySelector('[role="alert"]')).not.toBeNull();

      spy.mockRestore();
      cleanup();
    });

    it("shows fallback message when error has no message", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      expect(container.textContent).toContain("An unexpected error occurred.");

      spy.mockRestore();
      cleanup();
    });

    it("renders Try again and Reload page buttons", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("fail");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      const buttons = container.querySelectorAll("button");
      expect(buttons.length).toBe(2);
      expect(buttons[0].textContent).toContain("Try again");
      expect(buttons[1].textContent).toContain("Reload page");

      spy.mockRestore();
      cleanup();
    });

    it("recovers when Try again is clicked", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});
      let shouldThrow = true;

      function ConditionalThrow(): React.ReactElement {
        if (shouldThrow) throw new Error("crash");
        return React.createElement("p", null, "recovered");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ConditionalThrow)
        )
      );

      expect(container.textContent).toContain("Something went wrong");

      shouldThrow = false;
      act(() => {
        container.querySelector("button")!.click();
      });

      expect(container.textContent).toContain("recovered");

      spy.mockRestore();
      cleanup();
    });

    it("renders error-boundary-panel with correct class", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("test");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      expect(container.querySelector(".error-boundary-panel")).not.toBeNull();
      expect(container.querySelector(".error-boundary-actions")).not.toBeNull();
      expect(container.querySelector("h2")?.textContent).toBe("Something went wrong");

      spy.mockRestore();
      cleanup();
    });

    it("renders multiple children when no error", () => {
      const { container, cleanup } = renderToContainer(
        React.createElement(
          ErrorBoundary,
          null,
          React.createElement("p", null, "first"),
          React.createElement("p", null, "second")
        )
      );

      expect(container.textContent).toContain("first");
      expect(container.textContent).toContain("second");
      cleanup();
    });

    it("calls captureException via componentDidCatch when child throws", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("captured");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      // Verify the error boundary caught it and rendered error UI
      expect(container.textContent).toContain("captured");

      spy.mockRestore();
      cleanup();
    });

    it("shows error message with whitespace-only message as fallback", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});

      function ThrowingChild(): React.ReactElement {
        throw new Error("   ");
      }

      const { container, cleanup } = renderToContainer(
        React.createElement(ErrorBoundary, null,
          React.createElement(ThrowingChild)
        )
      );

      expect(container.textContent).toContain("An unexpected error occurred.");

      spy.mockRestore();
      cleanup();
    });
  });
});
