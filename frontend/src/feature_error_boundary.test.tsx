import React from "react";
import { describe, expect, it, vi } from "vitest";
import { createRoot } from "react-dom/client";
import { act } from "react";
import { FeatureErrorBoundary } from "./feature_error_boundary";

function renderToContainer(element: React.ReactElement): {
  container: HTMLDivElement;
  cleanup: () => void;
} {
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

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }): React.ReactElement {
  if (shouldThrow) throw new Error("test crash");
  return <p>working</p>;
}

describe("FeatureErrorBoundary", () => {
  it("renders children when no error", () => {
    const { container, cleanup } = renderToContainer(
      <FeatureErrorBoundary featureName="Test">
        <p>child content</p>
      </FeatureErrorBoundary>
    );

    expect(container.textContent).toContain("child content");
    cleanup();
  });

  it("renders error UI with feature name when child throws", () => {
    // Suppress React error boundary console noise
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { container, cleanup } = renderToContainer(
      <FeatureErrorBoundary featureName="Dynasty Calculator">
        <ThrowingChild shouldThrow={true} />
      </FeatureErrorBoundary>
    );

    expect(container.textContent).toContain("Dynasty Calculator encountered an error");
    expect(container.textContent).toContain("test crash");
    expect(container.querySelector("button")!.textContent).toContain("Try again");

    spy.mockRestore();
    cleanup();
  });

  it("recovers when Try again is clicked", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;

    function ConditionalThrow(): React.ReactElement {
      if (shouldThrow) throw new Error("boom");
      return <p>recovered</p>;
    }

    const { container, cleanup } = renderToContainer(
      <FeatureErrorBoundary featureName="Test">
        <ConditionalThrow />
      </FeatureErrorBoundary>
    );

    expect(container.textContent).toContain("encountered an error");

    shouldThrow = false;
    act(() => {
      container.querySelector("button")!.click();
    });

    expect(container.textContent).toContain("recovered");

    spy.mockRestore();
    cleanup();
  });
});
