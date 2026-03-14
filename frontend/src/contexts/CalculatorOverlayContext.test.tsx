import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";
import { CalculatorOverlayContext, useCalculatorOverlayContext } from "./CalculatorOverlayContext";

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

describe("CalculatorOverlayContext", () => {
  it("exports CalculatorOverlayContext", () => {
    expect(CalculatorOverlayContext).toBeDefined();
  });

  it("exports useCalculatorOverlayContext hook", () => {
    expect(typeof useCalculatorOverlayContext).toBe("function");
  });

  it("throws when used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    let caughtError: Error | null = null;

    function TestComponent(): React.ReactElement {
      try {
        useCalculatorOverlayContext();
      } catch (e) {
        caughtError = e as Error;
      }
      return React.createElement("div", null, "test");
    }

    const { cleanup } = renderToContainer(React.createElement(TestComponent));
    expect(caughtError).not.toBeNull();
    expect(caughtError!.message).toContain("useCalculatorOverlayContext must be used within CalculatorOverlayContext.Provider");
    spy.mockRestore();
    cleanup();
  });

  it("provides context value when wrapped in provider", () => {
    let receivedValue: unknown = null;

    function TestConsumer(): React.ReactElement {
      receivedValue = useCalculatorOverlayContext();
      return React.createElement("div", null, "consumer");
    }

    const mockValue = {
      overlayData: null,
      overlayLoading: false,
      overlayError: null,
      clearOverlay: vi.fn(),
      fetchOverlay: vi.fn(),
      overlayDataVersion: 0,
    };

    const { cleanup } = renderToContainer(
      React.createElement(
        CalculatorOverlayContext.Provider,
        { value: mockValue as never },
        React.createElement(TestConsumer)
      )
    );

    expect(receivedValue).toBe(mockValue);
    cleanup();
  });

  it("default context value is null", () => {
    // Directly check the context default
    let contextValue: unknown = "not-set";

    function TestComponent(): React.ReactElement {
      contextValue = React.useContext(CalculatorOverlayContext);
      return React.createElement("div", null, "test");
    }

    const { cleanup } = renderToContainer(React.createElement(TestComponent));
    expect(contextValue).toBeNull();
    cleanup();
  });
});
