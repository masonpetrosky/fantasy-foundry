import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { VisuallyHidden, MenuButton, SortableHeaderCell, useMenuInteractions } from "./accessibility_components";

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

describe("VisuallyHidden", () => {
  it("renders a span by default with sr-only class", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(VisuallyHidden, null, "hidden text")
    );
    const span = container.querySelector("span.sr-only");
    expect(span).not.toBeNull();
    expect(span!.textContent).toBe("hidden text");
    cleanup();
  });

  it("renders with custom element tag via as prop", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(VisuallyHidden, { as: "label" }, "label text")
    );
    const label = container.querySelector("label.sr-only");
    expect(label).not.toBeNull();
    expect(label!.textContent).toBe("label text");
    cleanup();
  });

  it("merges additional className with sr-only", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(VisuallyHidden, { className: "custom-class" }, "text")
    );
    const span = container.querySelector("span");
    expect(span!.className).toBe("sr-only custom-class");
    cleanup();
  });

  it("renders with sr-only only when className is empty", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(VisuallyHidden, { className: "" }, "text")
    );
    const span = container.querySelector("span");
    expect(span!.className).toBe("sr-only");
    cleanup();
  });

  it("passes through htmlFor prop", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(VisuallyHidden, { as: "label", htmlFor: "my-input" }, "Label")
    );
    const label = container.querySelector("label");
    expect(label!.getAttribute("for")).toBe("my-input");
    cleanup();
  });
});

describe("MenuButton", () => {
  it("renders a button with aria attributes", () => {
    const onToggle = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-1",
        open: false,
        onToggle,
        label: "Open Menu",
      })
    );
    const button = container.querySelector("button");
    expect(button).not.toBeNull();
    expect(button!.getAttribute("aria-haspopup")).toBe("menu");
    expect(button!.getAttribute("aria-expanded")).toBe("false");
    expect(button!.getAttribute("aria-controls")).toBe("menu-1");
    expect(button!.textContent).toContain("Open Menu");
    cleanup();
  });

  it("sets aria-expanded to true when open", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-2",
        open: true,
        onToggle: vi.fn(),
      })
    );
    const button = container.querySelector("button");
    expect(button!.getAttribute("aria-expanded")).toBe("true");
    cleanup();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-3",
        open: false,
        onToggle,
      })
    );
    act(() => {
      container.querySelector("button")!.click();
    });
    expect(onToggle).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("renders children content", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-4",
        open: false,
        onToggle: vi.fn(),
      }, "Child content")
    );
    expect(container.textContent).toContain("Child content");
    cleanup();
  });

  it("accepts custom hasPopup value", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-5",
        open: false,
        onToggle: vi.fn(),
        hasPopup: "listbox",
      })
    );
    expect(container.querySelector("button")!.getAttribute("aria-haspopup")).toBe("listbox");
    cleanup();
  });

  it("passes className to button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MenuButton, {
        controlsId: "menu-6",
        open: false,
        onToggle: vi.fn(),
        className: "custom-btn",
      })
    );
    expect(container.querySelector("button")!.className).toBe("custom-btn");
    cleanup();
  });
});

describe("SortableHeaderCell", () => {
  function renderInTable(element: React.ReactElement) {
    return renderToContainer(
      React.createElement("table", null,
        React.createElement("thead", null,
          React.createElement("tr", null, element)
        )
      )
    );
  }

  it("renders a th with sort button", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "name",
        label: "Name",
        sortCol: "name",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const th = container.querySelector("th");
    expect(th).not.toBeNull();
    expect(th!.getAttribute("aria-sort")).toBe("ascending");
    expect(container.textContent).toContain("Name");
    cleanup();
  });

  it("shows descending sort", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "age",
        label: "Age",
        sortCol: "age",
        sortDir: "desc",
        onSort: vi.fn(),
      })
    );
    const th = container.querySelector("th");
    expect(th!.getAttribute("aria-sort")).toBe("descending");
    cleanup();
  });

  it("shows none when not sorted column", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "name",
        label: "Name",
        sortCol: "age",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const th = container.querySelector("th");
    expect(th!.getAttribute("aria-sort")).toBe("none");
    cleanup();
  });

  it("calls onSort with column key when button clicked", () => {
    const onSort = vi.fn();
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "team",
        label: "Team",
        sortCol: "name",
        sortDir: "asc",
        onSort,
      })
    );
    act(() => {
      container.querySelector("button")!.click();
    });
    expect(onSort).toHaveBeenCalledWith("team");
    cleanup();
  });

  it("renders sort arrow when sorted ascending", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "val",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const arrow = container.querySelector(".sort-arrow");
    expect(arrow).not.toBeNull();
    expect(arrow!.textContent).toBe("\u25B2");
    cleanup();
  });

  it("renders sort arrow when sorted descending", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "val",
        sortDir: "desc",
        onSort: vi.fn(),
      })
    );
    const arrow = container.querySelector(".sort-arrow");
    expect(arrow!.textContent).toBe("\u25BC");
    cleanup();
  });

  it("does not render sort arrow when not sorted", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "other",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const arrow = container.querySelector(".sort-arrow");
    expect(arrow).toBeNull();
    cleanup();
  });

  it("renders VisuallyHidden sorted text when active", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "val",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const srOnly = container.querySelector(".sr-only");
    expect(srOnly).not.toBeNull();
    expect(srOnly!.textContent).toContain("Sorted ascending");
    cleanup();
  });

  it("applies custom className", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "other",
        sortDir: "asc",
        onSort: vi.fn(),
        className: "custom-col",
      })
    );
    const th = container.querySelector("th");
    expect(th!.className).toContain("custom-col");
    cleanup();
  });

  it("has correct aria-label describing next sort direction", () => {
    const { container, cleanup } = renderInTable(
      React.createElement(SortableHeaderCell, {
        columnKey: "val",
        label: "Value",
        sortCol: "val",
        sortDir: "asc",
        onSort: vi.fn(),
      })
    );
    const button = container.querySelector("button");
    expect(button!.getAttribute("aria-label")).toContain("descending");
    cleanup();
  });
});

describe("useMenuInteractions", () => {
  function TestComponent({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
    const menuRef = React.useRef<HTMLDivElement>(null);
    const triggerRef = React.useRef<HTMLButtonElement>(null);
    useMenuInteractions({ open, setOpen, menuRef, triggerRef });
    return React.createElement("div", null,
      React.createElement("button", { ref: triggerRef, "data-testid": "trigger" }, "Trigger"),
      open && React.createElement("div", { ref: menuRef, "data-testid": "menu" },
        React.createElement("button", { "data-testid": "item1" }, "Item 1"),
        React.createElement("button", { "data-testid": "item2" }, "Item 2"),
      )
    );
  }

  it("closes menu on Escape key", () => {
    const setOpen = vi.fn();
    const { cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: true, setOpen })
    );
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(setOpen).toHaveBeenCalledWith(false);
    cleanup();
  });

  it("closes menu on outside click", () => {
    const setOpen = vi.fn();
    const { cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: true, setOpen })
    );
    act(() => {
      document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(setOpen).toHaveBeenCalledWith(false);
    cleanup();
  });

  it("does not close when clicking inside menu", () => {
    const setOpen = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: true, setOpen })
    );
    const menu = container.querySelector('[data-testid="menu"]');
    act(() => {
      menu!.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(setOpen).not.toHaveBeenCalled();
    cleanup();
  });

  it("does not add listeners when closed", () => {
    const setOpen = vi.fn();
    const { cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: false, setOpen })
    );
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(setOpen).not.toHaveBeenCalled();
    cleanup();
  });

  it("handles ArrowDown to focus next item", () => {
    const setOpen = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: true, setOpen })
    );
    const item1 = container.querySelector('[data-testid="item1"]') as HTMLElement;
    item1.focus();
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    });
    // item2 should be focused
    const item2 = container.querySelector('[data-testid="item2"]') as HTMLElement;
    expect(document.activeElement).toBe(item2);
    cleanup();
  });

  it("handles ArrowUp to focus previous item", () => {
    const setOpen = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(TestComponent, { open: true, setOpen })
    );
    const item2 = container.querySelector('[data-testid="item2"]') as HTMLElement;
    item2.focus();
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
    });
    const item1 = container.querySelector('[data-testid="item1"]') as HTMLElement;
    expect(document.activeElement).toBe(item1);
    cleanup();
  });
});
