import { useCallback, useEffect, useRef, useState } from "react";

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
const DISMISS_THRESHOLD = 0.4;

/**
 * Resolve whether the user prefers reduced motion.
 * Exported for testing.
 */
export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Hook for a mobile bottom sheet with drag-to-dismiss, focus trap,
 * body scroll lock, and escape-to-close.
 */
export function useBottomSheet() {
  const [isOpen, setIsOpen] = useState(false);
  const sheetRef = useRef(null);
  const previousFocusRef = useRef(null);
  const dragStartYRef = useRef(null);
  const [dragOffset, setDragOffset] = useState(0);

  const open = useCallback(() => {
    previousFocusRef.current = document.activeElement;
    setIsOpen(true);
    setDragOffset(0);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setDragOffset(0);
    previousFocusRef.current?.focus();
  }, []);

  // Body scroll lock
  useEffect(() => {
    if (!isOpen) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [isOpen]);

  // Focus trap + escape
  useEffect(() => {
    if (!isOpen) return;
    requestAnimationFrame(() => sheetRef.current?.focus());

    const handler = (e) => {
      if (e.key === "Escape") {
        close();
        return;
      }
      if (e.key === "Tab" && sheetRef.current) {
        const focusable = Array.from(
          sheetRef.current.querySelectorAll(FOCUSABLE_SELECTOR),
        ).filter((el) => !el.disabled);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first || document.activeElement === sheetRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last || document.activeElement === sheetRef.current) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, close]);

  // Drag handle touch events
  const onTouchStart = useCallback((e) => {
    dragStartYRef.current = e.touches[0].clientY;
  }, []);

  const onTouchMove = useCallback((e) => {
    if (dragStartYRef.current == null) return;
    const delta = e.touches[0].clientY - dragStartYRef.current;
    setDragOffset(Math.max(0, delta));
  }, []);

  const onTouchEnd = useCallback(() => {
    if (dragStartYRef.current == null) return;
    const viewportHeight = window.innerHeight;
    if (dragOffset > viewportHeight * DISMISS_THRESHOLD) {
      close();
    } else {
      setDragOffset(0);
    }
    dragStartYRef.current = null;
  }, [close, dragOffset]);

  const dragHandleProps = {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
  };

  const sheetStyle = dragOffset > 0
    ? { transform: `translateY(${dragOffset}px)`, transition: "none" }
    : undefined;

  return { isOpen, open, close, sheetRef, dragHandleProps, sheetStyle };
}
