import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../test/a11y-helpers";
import { AppHeader } from "./AppHeader";

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

function defaultProps(): React.ComponentProps<typeof AppHeader> {
  return {
    section: "projections",
    setSection: vi.fn(),
    theme: "dark",
    toggleTheme: vi.fn(),
    authReady: true,
    authUser: null,
    authStatus: "idle",
    cloudStatus: "idle",
    signIn: vi.fn().mockResolvedValue(undefined),
    signUp: vi.fn().mockResolvedValue(undefined),
    signOut: vi.fn().mockResolvedValue(undefined),
    accountMenuOpen: false,
    setAccountMenuOpen: vi.fn(),
    accountMenuRef: { current: null },
    accountTriggerRef: { current: null },
    mobileNavOpen: false,
    setMobileNavOpen: vi.fn(),
    mobileNavMenuRef: { current: null },
    mobileNavTriggerRef: { current: null },
  };
}

describe("AppHeader a11y", () => {
  it("passes axe checks in default state", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(AppHeader, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with authenticated user", async () => {
    const props = defaultProps();
    props.authUser = { email: "test@example.com", id: "123" };
    const { container, cleanup } = renderToContainer(
      React.createElement(AppHeader, props),
    );
    await checkA11y(container);
    cleanup();
  });
});
