import React, { useCallback, useEffect, useRef } from "react";

interface MobileCalculatorSheetProps {
  isOpen: boolean;
  onClose: () => void;
  sheetRef: React.Ref<HTMLDivElement>;
  dragHandleProps: React.HTMLAttributes<HTMLDivElement>;
  sheetStyle?: React.CSSProperties;
  children: React.ReactNode;
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const MobileCalculatorSheet = React.memo(function MobileCalculatorSheet({
  isOpen,
  onClose,
  sheetRef,
  dragHandleProps,
  sheetStyle,
  children,
}: MobileCalculatorSheetProps): React.ReactElement | null {
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      dialogRef.current = node;
      if (typeof sheetRef === "function") {
        sheetRef(node);
      } else if (sheetRef && typeof sheetRef === "object") {
        (sheetRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }
    },
    [sheetRef],
  );

  // Escape key to close
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Focus trap: keep Tab/Shift+Tab within the dialog
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;
    const dialog = dialogRef.current;
    dialog.focus();

    const handleTab = (e: KeyboardEvent): void => {
      if (e.key !== "Tab") return;
      const focusable = dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    dialog.addEventListener("keydown", handleTab);
    return () => dialog.removeEventListener("keydown", handleTab);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      <div
        className="mobile-sheet-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className="mobile-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Dynasty Calculator"
        tabIndex={-1}
        ref={setRefs}
        style={sheetStyle}
      >
        <div className="mobile-sheet-handle" {...dragHandleProps}>
          <span className="sr-only">Drag to dismiss</span>
        </div>
        <div className="mobile-sheet-header">
          <span className="mobile-sheet-title">League Settings</span>
          <button
            type="button"
            className="inline-btn mobile-sheet-close"
            onClick={onClose}
            aria-label="Close calculator"
          >
            Close
          </button>
        </div>
        <div className="mobile-sheet-content">
          {children}
        </div>
      </div>
    </>
  );
});
