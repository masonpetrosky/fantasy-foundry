import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("../supabase_client", () => ({
  AUTH_SYNC_ENABLED: true,
}));
vi.mock("../account_panel", () => ({
  AccountPanel: () => React.createElement("div", { "data-testid": "account-panel" }, "AccountPanel"),
}));

import { AppHeader, AppHeaderProps } from "./AppHeader";

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

function makeProps(overrides: Partial<AppHeaderProps> = {}): AppHeaderProps {
  return {
    section: "projections",
    setSection: vi.fn(),
    theme: "dark",
    toggleTheme: vi.fn(),
    authReady: true,
    authUser: null,
    authStatus: "",
    cloudStatus: "",
    signIn: vi.fn(async () => {}),
    signUp: vi.fn(async () => {}),
    signOut: vi.fn(async () => {}),
    accountMenuOpen: false,
    setAccountMenuOpen: vi.fn(),
    accountMenuRef: React.createRef<HTMLDivElement>(),
    accountTriggerRef: React.createRef<HTMLButtonElement>(),
    mobileNavOpen: false,
    setMobileNavOpen: vi.fn(),
    mobileNavMenuRef: React.createRef<HTMLDivElement>(),
    mobileNavTriggerRef: React.createRef<HTMLButtonElement>(),
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppHeader", () => {
  it("renders header element", () => {
    const { container, cleanup } = renderToContainer(<AppHeader {...makeProps()} />);
    expect(container.querySelector("header")).not.toBeNull();
    cleanup();
  });

  it("renders skip link", () => {
    const { container, cleanup } = renderToContainer(<AppHeader {...makeProps()} />);
    const skipLink = container.querySelector(".skip-link") as HTMLAnchorElement;
    expect(skipLink).not.toBeNull();
    expect(skipLink.textContent).toBe("Skip to main content");
    expect(skipLink.href).toContain("#main-content");
    cleanup();
  });

  it("renders brand with Fantasy Foundry text", () => {
    const { container, cleanup } = renderToContainer(<AppHeader {...makeProps()} />);
    expect(container.textContent).toContain("Fantasy Foundry");
    expect(container.textContent).toContain("Dynasty Baseball Intelligence");
    cleanup();
  });

  it("renders primary navigation buttons", () => {
    const { container, cleanup } = renderToContainer(<AppHeader {...makeProps()} />);
    const nav = container.querySelector(".primary-nav");
    expect(nav).not.toBeNull();
    expect(nav!.textContent).toContain("Projections");
    expect(nav!.textContent).toContain("Methodology");
    cleanup();
  });

  it("marks active section button", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ section: "projections" })} />
    );
    const activeBtn = container.querySelector(".primary-nav-btn.active");
    expect(activeBtn).not.toBeNull();
    expect(activeBtn!.textContent).toBe("Projections");
    cleanup();
  });

  it("calls setSection when nav button clicked", () => {
    const setSection = vi.fn();
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ setSection })} />
    );
    const buttons = container.querySelectorAll(".primary-nav-btn");
    act(() => { (buttons[1] as HTMLButtonElement).click(); });
    expect(setSection).toHaveBeenCalledWith("methodology");
    cleanup();
  });

  it("renders theme toggle with correct label for dark mode", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ theme: "dark" })} />
    );
    const themeBtn = container.querySelector(".theme-toggle") as HTMLButtonElement;
    expect(themeBtn).not.toBeNull();
    expect(themeBtn.getAttribute("aria-label")).toBe("Switch to light mode");
    cleanup();
  });

  it("renders theme toggle with correct label for light mode", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ theme: "light" })} />
    );
    const themeBtn = container.querySelector(".theme-toggle") as HTMLButtonElement;
    expect(themeBtn.getAttribute("aria-label")).toBe("Switch to dark mode");
    cleanup();
  });

  it("calls toggleTheme when theme button clicked", () => {
    const toggleTheme = vi.fn();
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ toggleTheme })} />
    );
    act(() => { container.querySelector(".theme-toggle")!.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    expect(toggleTheme).toHaveBeenCalled();
    cleanup();
  });

  it("shows Sign In label when no auth user", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ authUser: null })} />
    );
    const accountBtn = container.querySelector(".account-menu-btn");
    expect(accountBtn!.textContent).toContain("Sign In");
    cleanup();
  });

  it("shows Account label when auth user is present", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ authUser: { email: "test@test.com" } })} />
    );
    const accountBtn = container.querySelector(".account-menu-btn");
    expect(accountBtn!.textContent).toContain("Account");
    expect(accountBtn!.textContent).toContain("Signed In");
    cleanup();
  });

  it("renders account panel when accountMenuOpen is true", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ accountMenuOpen: true })} />
    );
    expect(container.querySelector("#header-account-panel")).not.toBeNull();
    cleanup();
  });

  it("does not render account panel when accountMenuOpen is false", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ accountMenuOpen: false })} />
    );
    expect(container.querySelector("#header-account-panel")).toBeNull();
    cleanup();
  });

  it("renders mobile nav toggle", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps()} />
    );
    const mobileToggle = container.querySelector(".mobile-nav-toggle");
    expect(mobileToggle).not.toBeNull();
    expect(mobileToggle!.getAttribute("aria-label")).toBe("Navigation menu");
    cleanup();
  });

  it("shows mobile nav dropdown when mobileNavOpen is true", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ mobileNavOpen: true })} />
    );
    expect(container.querySelector("#mobile-nav-dropdown")).not.toBeNull();
    cleanup();
  });

  it("hides mobile nav dropdown when mobileNavOpen is false", () => {
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ mobileNavOpen: false })} />
    );
    expect(container.querySelector("#mobile-nav-dropdown")).toBeNull();
    cleanup();
  });

  it("brand click calls setSection with projections", () => {
    const setSection = vi.fn();
    const { container, cleanup } = renderToContainer(
      <AppHeader {...makeProps({ setSection })} />
    );
    const brand = container.querySelector(".brand") as HTMLAnchorElement;
    act(() => { brand.click(); });
    expect(setSection).toHaveBeenCalledWith("projections");
    cleanup();
  });
});
