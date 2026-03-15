import React, { useEffect, useRef } from "react";

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

    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        if (triggerRef?.current && typeof (triggerRef.current as HTMLElement).focus === "function") {
          (triggerRef.current as HTMLElement).focus();
        }
        return;
      }

      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const menu = menuRef?.current;
        if (!menu) return;
        const items = Array.from(
          menu.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [role="menuitem"]:not([disabled]), input:not([disabled]), a:not([disabled])',
          ),
        );
        if (items.length === 0) return;
        event.preventDefault();
        const current = document.activeElement as HTMLElement;
        const idx = items.indexOf(current);
        let next: number;
        if (event.key === "ArrowDown") {
          next = idx < 0 ? 0 : (idx + 1) % items.length;
        } else {
          next = idx < 0 ? items.length - 1 : (idx - 1 + items.length) % items.length;
        }
        items[next].focus();
      }
    };

    document.addEventListener("mousedown", onOutsideInteraction);
    document.addEventListener("touchstart", onOutsideInteraction);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onOutsideInteraction);
      document.removeEventListener("touchstart", onOutsideInteraction);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuRef, open, setOpen, triggerRef]);
}

/* ------------------------------------------------------------------ */
/*  useFocusTrap                                                      */
/* ------------------------------------------------------------------ */

const DEFAULT_FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

interface UseFocusTrapOptions {
  containerRef: React.RefObject<HTMLElement | null>;
  onEscape?: () => void;
  focusableSelector?: string;
  autoFocus?: boolean;
}

export function useFocusTrap({
  containerRef,
  onEscape,
  focusableSelector = DEFAULT_FOCUSABLE_SELECTOR,
  autoFocus = true,
}: UseFocusTrapOptions): void {
  const previousFocusRef = useRef<Element | null>(null);

  useEffect(() => {
    previousFocusRef.current = document.activeElement;
    const handler = (e: KeyboardEvent): void => {
      if (e.key === "Escape" && onEscape) {
        onEscape();
        return;
      }
      if (e.key === "Tab" && containerRef.current) {
        const focusable = Array.from(
          containerRef.current.querySelectorAll<HTMLElement>(focusableSelector),
        ).filter(el => !(el as HTMLButtonElement).disabled);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first || document.activeElement === containerRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last || document.activeElement === containerRef.current) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      (previousFocusRef.current as HTMLElement | null)?.focus();
    };
  }, [containerRef, focusableSelector, onEscape]);

  useEffect(() => {
    if (autoFocus) {
      containerRef.current?.focus();
    }
  }, [autoFocus, containerRef]);
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
