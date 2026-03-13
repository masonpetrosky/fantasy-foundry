import { describe, expect, it } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

import { useToastContext, ToastProvider } from "./Toast";

describe("Toast", () => {
  it("useToastContext returns null outside provider", () => {
    let contextValue: unknown = "unset";
    function TestComponent(): null {
      contextValue = useToastContext();
      return null;
    }
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(React.createElement(TestComponent));
    });
    expect(contextValue).toBeNull();
    act(() => root.unmount());
    document.body.removeChild(container);
  });

  it("ToastProvider renders children", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(
        React.createElement(ToastProvider, null,
          React.createElement("span", { "data-testid": "child" }, "Hello")
        )
      );
    });
    expect(container.querySelector("[data-testid='child']")!.textContent).toBe("Hello");
    act(() => root.unmount());
    document.body.removeChild(container);
  });

  it("exports useToastContext and ToastProvider", async () => {
    const mod = await import("./Toast");
    expect(typeof mod.useToastContext).toBe("function");
    expect(typeof mod.ToastProvider).toBe("function");
  });

  it("renders toast when addToast is called and dismisses on button click", () => {
    let addToast: ((msg: string, opts?: { type?: "success" | "error" | "info" }) => number) | null = null;
    function Consumer(): null {
      const ctx = useToastContext();
      if (ctx) addToast = ctx.addToast;
      return null;
    }
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(
        React.createElement(ToastProvider, null,
          React.createElement(Consumer)
        )
      );
    });

    // Add a toast
    act(() => { addToast!("Test notification", { type: "success" }); });
    expect(container.querySelector(".toast-container")).not.toBeNull();
    expect(container.textContent).toContain("Test notification");

    // Dismiss the toast
    const dismissBtn = container.querySelector(".toast-dismiss") as HTMLButtonElement;
    expect(dismissBtn).not.toBeNull();
    act(() => { dismissBtn.click(); });
    // After dismiss, toast container should be gone (no toasts)
    expect(container.querySelector(".toast-container")).toBeNull();

    act(() => root.unmount());
    document.body.removeChild(container);
  });
});
