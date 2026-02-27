import React, { useEffect } from "react";

/* ------------------------------------------------------------------ */
/*  VisuallyHidden                                                    */
/* ------------------------------------------------------------------ */

interface VisuallyHiddenProps extends React.HTMLAttributes<HTMLElement> {
  as?: keyof React.JSX.IntrinsicElements;
  className?: string;
  htmlFor?: string;
}

export function VisuallyHidden({
  as: elementTag = "span",
  className = "",
  ...props
}: VisuallyHiddenProps): React.ReactElement {
  const mergedClassName = ["sr-only", className].filter(Boolean).join(" ");
  return React.createElement(elementTag, { className: mergedClassName, ...props });
}

/* ------------------------------------------------------------------ */
/*  MenuButton                                                        */
/* ------------------------------------------------------------------ */

interface MenuButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  controlsId: string;
  open: boolean;
  onToggle: () => void;
  buttonRef?: React.Ref<HTMLButtonElement>;
  hasPopup?: boolean | "true" | "false" | "dialog" | "grid" | "listbox" | "menu" | "tree";
  className?: string;
  label?: React.ReactNode;
  children?: React.ReactNode;
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
}: MenuButtonProps): React.ReactElement {
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

/* ------------------------------------------------------------------ */
/*  useMenuInteractions                                               */
/* ------------------------------------------------------------------ */

interface UseMenuInteractionsOptions {
  open: boolean;
  setOpen: (value: boolean) => void;
  menuRef?: React.RefObject<HTMLElement | null>;
  triggerRef?: React.RefObject<HTMLElement | null>;
}

export function useMenuInteractions({ open, setOpen, menuRef, triggerRef }: UseMenuInteractionsOptions): void {
  useEffect(() => {
    if (!open) return undefined;

    const onOutsideInteraction = (event: MouseEvent | TouchEvent): void => {
      const target = event.target as Node;
      const clickedMenu = Boolean(menuRef?.current && menuRef.current.contains(target));
      const clickedTrigger = Boolean(triggerRef?.current && triggerRef.current.contains(target));
      if (clickedMenu || clickedTrigger) return;
      setOpen(false);
    };

    const onEscape = (event: KeyboardEvent): void => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      if (triggerRef?.current && typeof (triggerRef.current as HTMLElement).focus === "function") {
        (triggerRef.current as HTMLElement).focus();
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

/* ------------------------------------------------------------------ */
/*  SortableHeaderCell                                                */
/* ------------------------------------------------------------------ */

interface SortableHeaderCellProps {
  columnKey: string;
  label: string;
  sortCol: string;
  sortDir: "asc" | "desc";
  onSort: (columnKey: string) => void;
  className?: string;
}

export function SortableHeaderCell({
  columnKey,
  label,
  sortCol,
  sortDir,
  onSort,
  className = "",
}: SortableHeaderCellProps): React.ReactElement {
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
            {sortDir === "asc" ? "\u25B2" : "\u25BC"}
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
