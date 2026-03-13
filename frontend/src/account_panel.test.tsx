import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { AccountPanel } from "./account_panel";

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

const baseProps = {
  authEnabled: true,
  authReady: true,
  authUser: null,
  authStatus: "",
  cloudStatus: "",
  onSignIn: vi.fn(async () => {}),
  onSignUp: vi.fn(async () => {}),
  onSignOut: vi.fn(async () => {}),
};

describe("AccountPanel", () => {
  it("is exported as a function", () => {
    expect(typeof AccountPanel).toBe("function");
  });

  it("shows disabled message when auth not enabled", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, { ...baseProps, authEnabled: false })
    );
    expect(container.textContent).toContain("currently disabled");
    cleanup();
  });

  it("shows checking session when not ready", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, { ...baseProps, authReady: false })
    );
    expect(container.textContent).toContain("Checking existing session");
    cleanup();
  });

  it("shows sign in form when no user", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, baseProps)
    );
    expect(container.querySelector('input[type="email"]')).not.toBeNull();
    expect(container.querySelector('input[type="password"]')).not.toBeNull();
    const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(submitBtn.textContent).toBe("Sign In");
    cleanup();
  });

  it("shows sign out button when user is logged in", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, {
        ...baseProps,
        authUser: { email: "test@example.com" },
      })
    );
    expect(container.textContent).toContain("test@example.com");
    expect(container.textContent).toContain("Sign Out");
    cleanup();
  });

  it("toggles between signin and signup mode", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, baseProps)
    );
    const toggleBtn = Array.from(container.querySelectorAll("button")).find(
      b => b.textContent === "Create New Login"
    ) as HTMLButtonElement;
    act(() => { toggleBtn.click(); });
    const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(submitBtn.textContent).toBe("Create Account");
    cleanup();
  });

  it("shows status text with error tone", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, { ...baseProps, authStatus: "Sign in failed" })
    );
    expect(container.textContent).toContain("Sign in failed");
    const statusEl = container.querySelector(".account-status");
    expect(statusEl?.classList.contains("error")).toBe(true);
    cleanup();
  });

  it("shows status text with ok tone", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, {
        ...baseProps,
        authUser: { email: "test@test.com" },
        cloudStatus: "Preferences saved",
      })
    );
    const statusEl = container.querySelector(".account-status");
    expect(statusEl?.classList.contains("ok")).toBe(true);
    cleanup();
  });

  it("renders Account Sync heading", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AccountPanel, baseProps)
    );
    expect(container.querySelector("h3")?.textContent).toBe("Account Sync");
    cleanup();
  });
});
