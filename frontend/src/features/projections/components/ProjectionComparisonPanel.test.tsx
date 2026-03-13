import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionComparisonPanel } from "./ProjectionComparisonPanel";

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

function defaultProps(overrides: Partial<React.ComponentProps<typeof ProjectionComparisonPanel>> = {}) {
  return {
    compareRows: [] as Record<string, unknown>[],
    maxComparePlayers: 4,
    comparisonColumns: ["DynastyValue", "Age"],
    colLabels: { DynastyValue: "Dynasty Value", Age: "Age" },
    formatCellValue: (col: string, val: unknown) => String(val ?? ""),
    removeCompareRow: vi.fn(),
    copyCompareShareLink: null,
    ...overrides,
  };
}

describe("ProjectionComparisonPanel", () => {
  it("is exported", () => {
    expect(ProjectionComparisonPanel).toBeTruthy();
  });

  it("returns null when compareRows is empty", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(React.createElement(ProjectionComparisonPanel, defaultProps()));
    });
    expect(container.innerHTML).toBe("");
    act(() => root.unmount());
    document.body.removeChild(container);
  });

  it("renders comparison panel when rows are present", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Julio Rodriguez", Team: "SEA", Pos: "OF", DynastyValue: 42, Age: 25, Year: 2029 },
        ],
      }))
    );
    expect(container.querySelector(".comparison-panel")).not.toBeNull();
    expect(container.textContent).toContain("Player Comparison");
    expect(container.textContent).toContain("Julio Rodriguez");
    cleanup();
  });

  it("shows count of selected players", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Player A", Team: "SEA", Pos: "OF", Year: 2029 },
          { Player: "Player B", Team: "NYY", Pos: "SS", Year: 2029 },
        ],
        maxComparePlayers: 4,
      }))
    );
    expect(container.textContent).toContain("2/4 selected");
    cleanup();
  });

  it("renders remove button for each player", () => {
    const removeFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Player A", Team: "SEA", Pos: "OF", Year: 2029 },
        ],
        removeCompareRow: removeFn,
      }))
    );
    const removeBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Remove");
    expect(removeBtn).toBeDefined();
    act(() => {
      removeBtn!.click();
    });
    expect(removeFn).toHaveBeenCalled();
    cleanup();
  });

  it("renders comparison columns as dl items", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test", Team: "SEA", Pos: "OF", DynastyValue: 35, Age: 22, Year: 2029 },
        ],
      }))
    );
    const dts = container.querySelectorAll("dt");
    expect(dts.length).toBe(2); // DynastyValue and Age
    expect(dts[0].textContent).toBe("Dynasty Value");
    expect(dts[1].textContent).toBe("Age");
    cleanup();
  });

  it("renders Share button when copyCompareShareLink is provided", () => {
    const shareFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test", Team: "SEA", Pos: "OF", Year: 2029 },
        ],
        copyCompareShareLink: shareFn,
      }))
    );
    const shareBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Share");
    expect(shareBtn).toBeDefined();
    act(() => {
      shareBtn!.click();
    });
    expect(shareFn).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("does not render Share button when copyCompareShareLink is null", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test", Team: "SEA", Pos: "OF", Year: 2029 },
        ],
        copyCompareShareLink: null,
      }))
    );
    const shareBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Share");
    expect(shareBtn).toBeUndefined();
    cleanup();
  });

  it("renders team and position info", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test Player", Team: "LAD", Pos: "SP", Year: 2029 },
        ],
      }))
    );
    expect(container.textContent).toContain("LAD");
    expect(container.textContent).toContain("SP");
    cleanup();
  });

  it("shows dash for missing team", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "No Team", Pos: "OF", Year: 2029 },
        ],
      }))
    );
    expect(container.textContent).toContain("\u2014");
    cleanup();
  });

  it("renders region with aria-label", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test", Team: "SEA", Pos: "OF", Year: 2029 },
        ],
      }))
    );
    const region = container.querySelector('[role="region"]');
    expect(region).not.toBeNull();
    expect(region!.getAttribute("aria-label")).toBe("Player comparison");
    cleanup();
  });

  it("formats cell values using formatCellValue", () => {
    const formatCellValue = vi.fn((_col: string, val: unknown) => `formatted:${val}`);
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionComparisonPanel, defaultProps({
        compareRows: [
          { Player: "Test", Team: "SEA", Pos: "OF", DynastyValue: 42, Age: 25, Year: 2029 },
        ],
        formatCellValue,
      }))
    );
    expect(formatCellValue).toHaveBeenCalled();
    expect(container.textContent).toContain("formatted:42");
    cleanup();
  });
});
