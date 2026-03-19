import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";
import type { TierLimits } from "./premium";

vi.mock("./dynasty_calculator_tooltip", () => ({
  CalcTooltip: ({ label, children }: { label: string; children: React.ReactNode }) =>
    React.createElement("span", { "data-tooltip": label }, children),
}));
vi.mock("./dynasty_calculator_sidebar_categories", () => ({
  RotoCategoriesForm: () => React.createElement("div", { "data-testid": "roto-form" }),
}));
vi.mock("./dynasty_calculator_sidebar_points", () => ({
  PointsScoringForm: () => React.createElement("div", { "data-testid": "points-form" }),
}));
vi.mock("./dynasty_calculator_sidebar_slots", () => ({
  StarterSlotsForm: () => React.createElement("div", { "data-testid": "slots-form" }),
}));
vi.mock("./features/fantrax/LeagueConnectPanel", () => ({
  LeagueConnectPanel: () => React.createElement("div", { "data-testid": "fantrax-panel" }),
}));

import { DynastyCalculatorSidebar } from "./dynasty_calculator_sidebar";

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

function makeDefaultProps() {
  return {
    meta: { years: [2026, 2027, 2028, 2029, 2030] },
    presets: {},
    settings: {
      mode: "common",
      teams: 12,
      start_year: 2026,
      horizon: 10,
      scoring_mode: "roto",
      discount: 0.94,
      two_way: "sum",
      sims: 300,
      ip_min: 1000,
      ip_max: null as string | null,
      sgp_denominator_mode: "classic",
      sgp_winsor_low_pct: 0.1,
      sgp_winsor_high_pct: 0.9,
      sgp_epsilon_counting: 0.15,
      sgp_epsilon_ratio: 0.0015,
      enable_playing_time_reliability: false,
      enable_age_risk_adjustment: false,
      enable_prospect_risk_adjustment: false,
      enable_bench_stash_relief: false,
      bench_negative_penalty: 0.55,
      enable_ir_stash_relief: false,
      ir_negative_penalty: 0.2,
      enable_replacement_blend: false,
      replacement_blend_alpha: 0.7,
      bench: 5,
      minors: 5,
      ir: 2,
      auction_budget: null as number | null,
      // Slot settings
      C: 1, "1B": 1, "2B": 1, "3B": 1, SS: 1, OF: 3, UTIL: 1,
      SP: 5, RP: 2, P: 0,
      // Roto categories
      R: true, HR: true, RBI: true, SB: true, AVG: true,
      W: true, K: true, SV: true, ERA: true, WHIP: true,
      // Points settings
      points_rules: {},
    },
    state: {
      calculationNotice: "",
      canSavePreset: false,
      hittersPerTeam: 10,
      isPointsMode: false,
      lastRunTotal: 0,
      loading: false,
      mainTableOverlayActive: false,
      pointRulesCount: 0,
      presetName: "",
      presetStatus: "",
      presetStatusIsError: false,
      pitchersPerTeam: 7,
      reservePerTeam: 10,
      selectedPresetName: "",
      selectedRotoHitCategoryCount: 5,
      selectedRotoPitchCategoryCount: 5,
      status: "",
      statusIsError: false,
      totalPlayersPerTeam: 27,
      validationError: "",
      validationWarning: "",
      hasSuccessfulRun: false,
      tierLimits: null as TierLimits | null,
    },
    actions: {
      applyQuickStartAndRun: vi.fn(),
      applyScoringSetup: vi.fn(),
      clearAppliedValues: vi.fn(),
      copyShareLink: vi.fn(),
      deletePreset: vi.fn(),
      reapplySetupDefaults: vi.fn(),
      resetPointsScoringDefaults: vi.fn(),
      resetRotoCategoryDefaults: vi.fn(),
      run: vi.fn(),
      savePreset: vi.fn(),
      selectPreset: vi.fn(),
      setPresetName: vi.fn(),
      update: vi.fn(),
    },
    fantrax: null,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DynastyCalculatorSidebar", () => {
  it("renders League Settings heading", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("h3")!.textContent).toBe("League Settings");
    cleanup();
  });

  it("renders Quick Start buttons", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const buttons = Array.from(container.querySelectorAll("button")).map(b => b.textContent);
    expect(buttons).toContain("Run 12-Team 5x5 Roto");
    expect(buttons).toContain("Run 12-Team Points");
    expect(buttons).toContain("Run 12-Team Deep Dynasty");
    cleanup();
  });

  it("calls applyQuickStartAndRun when Quick Start clicked", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const rotoBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Run 12-Team 5x5 Roto")!;
    act(() => { rotoBtn.click(); });
    expect(props.actions.applyQuickStartAndRun).toHaveBeenCalledWith("roto");
    cleanup();
  });

  it("renders teams input with correct value", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const teamsInput = container.querySelector("#calc-teams-input") as HTMLInputElement;
    expect(teamsInput).not.toBeNull();
    expect(teamsInput.value).toBe("12");
    cleanup();
  });

  it("calls update when teams input changes", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const teamsInput = container.querySelector("#calc-teams-input") as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(teamsInput, "14");
      teamsInput.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(props.actions.update).toHaveBeenCalledWith("teams", "14");
    cleanup();
  });

  it("renders Run Dynasty Rankings button when no successful run", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const runBtn = container.querySelector(".calc-btn") as HTMLButtonElement;
    expect(runBtn.textContent).toContain("Run Dynasty Rankings");
    cleanup();
  });

  it("renders Apply To Main Table button after successful run", () => {
    const props = makeDefaultProps();
    props.state.hasSuccessfulRun = true;
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const runBtn = container.querySelector(".calc-btn") as HTMLButtonElement;
    expect(runBtn.textContent).toContain("Apply To Main Table");
    cleanup();
  });

  it("shows Computing... while loading", () => {
    const props = makeDefaultProps();
    props.state.loading = true;
    props.state.status = "Running simulations...";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const runBtn = container.querySelector(".calc-btn") as HTMLButtonElement;
    expect(runBtn.textContent).toContain("Computing...");
    expect(runBtn.disabled).toBe(true);
    cleanup();
  });

  it("disables run button when validation error", () => {
    const props = makeDefaultProps();
    props.state.validationError = "Teams must be at least 2";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const runBtn = container.querySelector(".calc-btn") as HTMLButtonElement;
    expect(runBtn.disabled).toBe(true);
    cleanup();
  });

  it("shows validation error in status area", () => {
    const props = makeDefaultProps();
    props.state.validationError = "Teams must be at least 2";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const statusDiv = container.querySelector(".calc-status");
    expect(statusDiv!.textContent).toContain("Fix settings: Teams must be at least 2");
    cleanup();
  });

  it("renders RotoCategoriesForm in roto mode", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("[data-testid='roto-form']")).not.toBeNull();
    expect(container.querySelector("[data-testid='points-form']")).toBeNull();
    cleanup();
  });

  it("renders PointsScoringForm in points mode", () => {
    const props = makeDefaultProps();
    props.state.isPointsMode = true;
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("[data-testid='points-form']")).not.toBeNull();
    expect(container.querySelector("[data-testid='roto-form']")).toBeNull();
    cleanup();
  });

  it("renders StarterSlotsForm", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("[data-testid='slots-form']")).not.toBeNull();
    cleanup();
  });

  it("renders summary grid with format info", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const text = container.textContent || "";
    expect(text).toContain("Roto Focused");
    expect(text).toContain("12");
    expect(text).toContain("27 slots");
    cleanup();
  });

  it("renders preset section", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.textContent).toContain("Presets And Sharing");
    expect(container.querySelector("#calc-preset-name")).not.toBeNull();
    cleanup();
  });

  it("calls run when Run button clicked", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const runBtn = container.querySelector(".calc-btn") as HTMLButtonElement;
    act(() => { runBtn.click(); });
    expect(props.actions.run).toHaveBeenCalled();
    cleanup();
  });

  it("calls copyShareLink when Copy Share Link clicked", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const shareBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Copy Share Link")!;
    act(() => { shareBtn.click(); });
    expect(props.actions.copyShareLink).toHaveBeenCalled();
    cleanup();
  });

  it("renders Clear Applied Values button disabled when overlay not active", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const clearBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Clear Applied Values")!;
    expect(clearBtn.hasAttribute("disabled")).toBe(true);
    cleanup();
  });

  it("renders fantrax panel when fantrax is provided", () => {
    const props = makeDefaultProps();
    props.fantrax = { applyLeagueSettings: vi.fn() } as never;
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("[data-testid='fantrax-panel']")).not.toBeNull();
    cleanup();
  });

  it("hides fantrax panel when fantrax is null", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("[data-testid='fantrax-panel']")).toBeNull();
    cleanup();
  });

  it("renders delete preset button when a preset is selected", () => {
    const props = makeDefaultProps();
    props.state.selectedPresetName = "My Preset";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const deleteBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Delete Selected Preset")!;
    expect(deleteBtn).toBeDefined();
    act(() => { deleteBtn.click(); });
    expect(props.actions.deletePreset).toHaveBeenCalledWith("My Preset");
    cleanup();
  });

  it("shows preset status message", () => {
    const props = makeDefaultProps();
    props.state.presetStatus = "Preset saved!";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.textContent).toContain("Preset saved!");
    cleanup();
  });

  it("shows preset status error with correct class", () => {
    const props = makeDefaultProps();
    props.state.presetStatus = "Failed to save";
    props.state.presetStatusIsError = true;
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const statusEl = container.querySelector(".calc-preset-status.error");
    expect(statusEl).not.toBeNull();
    cleanup();
  });

  it("renders calculation notice when provided", () => {
    const props = makeDefaultProps();
    props.state.calculationNotice = "Deep-roster fallback applied.";
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.textContent).toContain("Deep-roster fallback applied.");
    cleanup();
  });

  it("renders saved presets in the select dropdown", () => {
    const props = makeDefaultProps();
    props.presets = { "My League": {}, "Other League": {} };
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    const options = container.querySelectorAll("#calc-saved-presets option");
    const optionTexts = Array.from(options).map(o => o.textContent);
    expect(optionTexts).toContain("My League");
    expect(optionTexts).toContain("Other League");
    cleanup();
  });

  it("renders depth inputs (bench, minors, IR)", () => {
    const props = makeDefaultProps();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.querySelector("#calc-bench")).not.toBeNull();
    expect(container.querySelector("#calc-minors")).not.toBeNull();
    expect(container.querySelector("#calc-ir")).not.toBeNull();
    cleanup();
  });

  it("shows main table sync status when overlay active", () => {
    const props = makeDefaultProps();
    props.state.mainTableOverlayActive = true;
    props.state.lastRunTotal = 850;
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorSidebar {...props} />
    );
    expect(container.textContent).toContain("Custom calculator values are active");
    expect(container.textContent).toContain("850");
    cleanup();
  });
});
