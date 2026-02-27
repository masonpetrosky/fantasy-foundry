import React from "react";

type SectionTab = "all" | "bat" | "pitch";

interface ProjectionSectionTabsProps {
  tab: SectionTab;
  onSelectTab: (tab: SectionTab) => void;
}

export const ProjectionSectionTabs = React.memo(function ProjectionSectionTabs({
  tab,
  onSelectTab,
}: ProjectionSectionTabsProps): React.ReactElement {
  return (
    <div className="section-tabs">
      <button className={`section-tab ${tab === "all" ? "active" : ""}`} onClick={() => onSelectTab("all")} aria-pressed={tab === "all"}>All</button>
      <button className={`section-tab ${tab === "bat" ? "active" : ""}`} onClick={() => onSelectTab("bat")} aria-pressed={tab === "bat"}>Hitters</button>
      <button className={`section-tab ${tab === "pitch" ? "active" : ""}`} onClick={() => onSelectTab("pitch")} aria-pressed={tab === "pitch"}>Pitchers</button>
    </div>
  );
});
