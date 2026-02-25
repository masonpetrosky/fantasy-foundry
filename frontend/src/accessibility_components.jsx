import React, { useEffect } from "react";

export function VisuallyHidden({ as: elementTag = "span", className = "", ...props }) {
  const mergedClassName = ["sr-only", className].filter(Boolean).join(" ");
  return React.createElement(elementTag, { className: mergedClassName, ...props });
}

export function MenuButton({
  controlsId,
  open,
  onToggle,
  buttonRef,
  hasPopup = "menu",
  className,
  label,
  children,
  ...buttonProps
}) {
  return (
    <button
      type="button"
      ref={buttonRef}
      className={className}
      onClick={onToggle}
      aria-haspopup={hasPopup}
      aria-expanded={open}
      aria-controls={controlsId}
      {...buttonProps}
    >
      {label}
      {children}
    </button>
  );
}

export function useMenuInteractions({ open, setOpen, menuRef, triggerRef }) {
  useEffect(() => {
    if (!open) return undefined;

    const onOutsideInteraction = event => {
      const target = event.target;
      const clickedMenu = Boolean(menuRef?.current && menuRef.current.contains(target));
      const clickedTrigger = Boolean(triggerRef?.current && triggerRef.current.contains(target));
      if (clickedMenu || clickedTrigger) return;
      setOpen(false);
    };

    const onEscape = event => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      if (triggerRef?.current && typeof triggerRef.current.focus === "function") {
        triggerRef.current.focus();
      }
    };

    document.addEventListener("mousedown", onOutsideInteraction);
    document.addEventListener("touchstart", onOutsideInteraction);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onOutsideInteraction);
      document.removeEventListener("touchstart", onOutsideInteraction);
      document.removeEventListener("keydown", onEscape);
    };
  }, [menuRef, open, setOpen, triggerRef]);
}

export function SortableHeaderCell({
  columnKey,
  label,
  sortCol,
  sortDir,
  onSort,
  className = "",
}) {
  const isSorted = sortCol === columnKey;
  const ariaSortValue = isSorted ? (sortDir === "asc" ? "ascending" : "descending") : "none";
  const nextSortDirectionLabel = !isSorted || sortDir === "desc" ? "ascending" : "descending";
  const buttonAriaLabel = `${label}. Currently ${ariaSortValue}. Activate to sort ${nextSortDirectionLabel}.`;

  return (
    <th scope="col" className={className} aria-sort={ariaSortValue}>
      <button
        type="button"
        className="sort-header-btn"
        onClick={() => onSort(columnKey)}
        aria-label={buttonAriaLabel}
      >
        <span>{label}</span>
        {isSorted && (
          <span className="sort-arrow" aria-hidden="true">
            {sortDir === "asc" ? "▲" : "▼"}
          </span>
        )}
        {isSorted && (
          <VisuallyHidden>
            Sorted {sortDir === "asc" ? "ascending" : "descending"}
          </VisuallyHidden>
        )}
      </button>
    </th>
  );
}
