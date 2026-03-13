import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";

vi.mock("./analytics", () => ({ trackEvent: vi.fn() }));

import { NewsletterSignup } from "./NewsletterSignup";

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

describe("NewsletterSignup", () => {
  it("is exported as a function", () => {
    expect(typeof NewsletterSignup).toBe("function");
  });

  it("renders the signup form", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );
    expect(container.querySelector("form")).not.toBeNull();
    expect(container.querySelector('input[type="email"]')).not.toBeNull();
    expect(container.querySelector('button[type="submit"]')).not.toBeNull();
    cleanup();
  });

  it("renders label text", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );
    expect(container.textContent).toContain("Get dynasty insights");
    cleanup();
  });

  it("renders subscribe button text", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );
    const btn = container.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(btn.textContent).toBe("Subscribe");
    cleanup();
  });

  it("has accessible email label", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );
    const label = container.querySelector('label[for="newsletter-email"]');
    expect(label).not.toBeNull();
    cleanup();
  });

  it("updates email input on change", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );
    const input = container.querySelector('input[type="email"]') as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(input, "test@example.com");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    cleanup();
  });

  it("submits form and shows success message", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    ) as unknown as typeof fetch;

    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );

    // Type email
    const input = container.querySelector('input[type="email"]') as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(input, "user@example.com");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });

    // Submit form
    const form = container.querySelector("form") as HTMLFormElement;
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    await act(async () => {
      await new Promise(r => setTimeout(r, 0));
    });

    expect(container.textContent).toContain("subscribed");
    globalThis.fetch = originalFetch;
    cleanup();
  });

  it("shows error message on failed submission", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: "Already subscribed" }),
      })
    ) as unknown as typeof fetch;

    const { container, cleanup } = renderToContainer(
      React.createElement(NewsletterSignup, { apiBase: "http://test" })
    );

    const input = container.querySelector('input[type="email"]') as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(input, "user@example.com");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });

    const form = container.querySelector("form") as HTMLFormElement;
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    await act(async () => {
      await new Promise(r => setTimeout(r, 0));
    });

    expect(container.textContent).toContain("Already subscribed");
    globalThis.fetch = originalFetch;
    cleanup();
  });
});
