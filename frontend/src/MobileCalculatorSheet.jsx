import React from "react";

export const MobileCalculatorSheet = React.memo(function MobileCalculatorSheet({
  isOpen,
  onClose,
  sheetRef,
  dragHandleProps,
  sheetStyle,
  children,
}) {
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
        ref={sheetRef}
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
