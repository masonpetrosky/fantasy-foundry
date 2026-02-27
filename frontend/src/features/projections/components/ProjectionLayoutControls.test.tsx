import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ProjectionLayoutControls } from "./ProjectionLayoutControls";

describe("ProjectionLayoutControls", () => {
  it("shows current layout copy and card column chooser in card mode", () => {
    const html = renderToStaticMarkup(
      <ProjectionLayoutControls
        isMobileViewport
        mobileLayoutMode="cards"
        setMobileLayoutMode={vi.fn()}
        cardColumnCatalog={["Player", "DynastyValue"]}
        resolvedProjectionCardHiddenCols={{}}
        requiredProjectionCardCols={new Set(["Player"])}
        toggleProjectionCardColumn={vi.fn()}
        showAllProjectionCardColumns={vi.fn()}
        colLabels={{ DynastyValue: "Dynasty Value" }}
      />
    );

    expect(html).toContain("Layout");
    expect(html).toContain("Viewing Cards");
    expect(html).toContain("Card View");
    expect(html).toContain("Table View");
    expect(html).toContain("Card Stats (2/2)");
  });

  it("hides card column chooser outside card mode", () => {
    const html = renderToStaticMarkup(
      <ProjectionLayoutControls
        isMobileViewport={false}
        mobileLayoutMode="table"
        setMobileLayoutMode={vi.fn()}
        cardColumnCatalog={["Player", "DynastyValue"]}
        resolvedProjectionCardHiddenCols={{}}
        requiredProjectionCardCols={new Set(["Player"])}
        toggleProjectionCardColumn={vi.fn()}
        showAllProjectionCardColumns={vi.fn()}
        colLabels={{ DynastyValue: "Dynasty Value" }}
      />
    );

    expect(html).not.toContain("Card Stats");
  });
});
