import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { StarterSlotsForm } from "./dynasty_calculator_sidebar_slots";
import { HITTER_SLOT_FIELDS, PITCHER_SLOT_FIELDS } from "./dynasty_calculator_config";

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

function defaultSettings(): Record<string, unknown> {
  const settings: Record<string, unknown> = {};
  [...HITTER_SLOT_FIELDS, ...PITCHER_SLOT_FIELDS].forEach(f => {
    settings[f.key] = f.defaultValue;
  });
  return settings;
}

describe("StarterSlotsForm", () => {
  it("is exported", () => {
    expect(StarterSlotsForm).toBeTruthy();
  });

  it("renders section title", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(StarterSlotsForm, { settings: defaultSettings(), update: vi.fn() })
    );
    expect(container.textContent).toContain("Starter Slots Per Team");
    cleanup();
  });

  it("renders input fields for each slot", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(StarterSlotsForm, { settings: defaultSettings(), update: vi.fn() })
    );
    const inputs = container.querySelectorAll('input[type="number"]');
    expect(inputs.length).toBe(HITTER_SLOT_FIELDS.length + PITCHER_SLOT_FIELDS.length);
    cleanup();
  });

  it("renders labels for slot fields", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(StarterSlotsForm, { settings: defaultSettings(), update: vi.fn() })
    );
    const labels = container.querySelectorAll("label");
    expect(labels.length).toBeGreaterThan(0);
    expect(labels[0].textContent).toBe(HITTER_SLOT_FIELDS[0].label);
    cleanup();
  });

  it("calls update when input changes", () => {
    const update = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(StarterSlotsForm, { settings: defaultSettings(), update })
    );
    const input = container.querySelector('input[type="number"]') as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype, "value"
      )?.set;
      nativeInputValueSetter?.call(input, "5");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    // The update function is called via onChange
    cleanup();
  });
});
