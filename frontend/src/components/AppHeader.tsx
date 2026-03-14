import React from "react";
import { AUTH_SYNC_ENABLED } from "../supabase_client";
import { AccountPanel } from "../account_panel";
import { PRIMARY_NAV_ITEMS } from "../app_content";

export interface AppHeaderProps {
  section: string;
  setSection: (section: string) => void;
  theme: string;
  toggleTheme: () => void;
  authReady: boolean;
  authUser: { email?: string; [key: string]: unknown } | null;
  authStatus: string;
  cloudStatus: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  accountMenuOpen: boolean;
  setAccountMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  accountMenuRef: React.RefObject<HTMLDivElement | null>;
  accountTriggerRef: React.RefObject<HTMLButtonElement | null>;
  mobileNavOpen: boolean;
  setMobileNavOpen: React.Dispatch<React.SetStateAction<boolean>>;
  mobileNavMenuRef: React.RefObject<HTMLDivElement | null>;
  mobileNavTriggerRef: React.RefObject<HTMLButtonElement | null>;
}

export const AppHeader = React.memo(function AppHeader({
  section,
  setSection,
  theme,
  toggleTheme,
  authReady,
  authUser,
  authStatus,
  cloudStatus,
  signIn,
  signUp,
  signOut,
  accountMenuOpen,
  setAccountMenuOpen,
  accountMenuRef,
  accountTriggerRef,
  mobileNavOpen,
  setMobileNavOpen,
  mobileNavMenuRef,
  mobileNavTriggerRef,
}: AppHeaderProps): React.ReactElement {
  const accountMenuLabel = !AUTH_SYNC_ENABLED || authUser ? "Account" : "Sign In";

  return (
    <header>
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <div className="nav-inner">
        <a
          className="brand"
          href="#"
          onClick={event => {
            event.preventDefault();
            setSection("projections");
          }}
          aria-label="Fantasy Foundry home"
        >
          <span className="brand-mark" aria-hidden="true">
            <img src="/assets/favicon.svg" alt="" />
          </span>
          <span className="brand-text">
            <span className="brand-title">Fantasy Foundry</span>
            <span className="brand-tagline">Dynasty Baseball Intelligence</span>
          </span>
        </a>
        <nav className="primary-nav" aria-label="Main navigation">
          <div className="primary-nav-scroll">
            {PRIMARY_NAV_ITEMS.map(item => (
              <button
                key={item.key}
                type="button"
                className={`primary-nav-btn ${section === item.key ? "active" : ""}`.trim()}
                onClick={() => setSection(item.key)}
                aria-pressed={section === item.key}
              >
                {item.label}
              </button>
            ))}
          </div>
        </nav>
        <div className="mobile-nav-menu" ref={mobileNavMenuRef}>
          <button
            type="button"
            ref={mobileNavTriggerRef}
            className={`inline-btn mobile-nav-toggle${mobileNavOpen ? " open" : ""}`}
            onClick={() => setMobileNavOpen(prev => !prev)}
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-nav-dropdown"
            aria-label="Navigation menu"
          >
            <span aria-hidden="true">{mobileNavOpen ? "\u2715" : "\u2630"}</span>
          </button>
          {mobileNavOpen && (
            <nav id="mobile-nav-dropdown" className="mobile-nav-dropdown" aria-label="Main navigation">
              {PRIMARY_NAV_ITEMS.map(item => (
                <button
                  key={item.key}
                  type="button"
                  className={`mobile-nav-item${section === item.key ? " active" : ""}`}
                  onClick={() => setSection(item.key)}
                  aria-pressed={section === item.key}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          )}
        </div>
        <button
          type="button"
          className="inline-btn theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? "\u2600" : "\u263E"}
        </button>
        <div className="account-menu" ref={accountMenuRef}>
          <button
            type="button"
            ref={accountTriggerRef}
            className={`inline-btn account-menu-btn ${accountMenuOpen ? "open" : ""}`.trim()}
            onClick={() => setAccountMenuOpen(open => !open)}
            aria-expanded={accountMenuOpen}
            aria-controls="header-account-panel"
          >
            <span>{accountMenuLabel}</span>
            {authUser && <span className="account-menu-pill">Signed In</span>}
          </button>
          {accountMenuOpen && (
            <div id="header-account-panel" className="account-popover" role="region" aria-label="Account">
              <AccountPanel
                authEnabled={AUTH_SYNC_ENABLED}
                authReady={authReady}
                authUser={authUser}
                authStatus={authStatus}
                cloudStatus={cloudStatus}
                onSignIn={signIn}
                onSignUp={signUp}
                onSignOut={signOut}
              />
            </div>
          )}
        </div>
      </div>
    </header>
  );
});
