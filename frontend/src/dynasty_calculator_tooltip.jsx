import React, { useCallback, useEffect, useRef, useState } from "react";

export function CalcTooltip({ label, children }) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        close();
      }
    }
    function handleKey(e) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open, close]);

  return (
    <span className="calc-tooltip-wrapper" ref={wrapperRef}>
      <button
        type="button"
        className="calc-method-link"
        onClick={() => setOpen(prev => !prev)}
        aria-expanded={open}
      >
        {label}
      </button>
      {open && (
        <span className="calc-tooltip-popup" role="tooltip">
          {children}
        </span>
      )}
    </span>
  );
}
