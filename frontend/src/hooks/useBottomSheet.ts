import { useCallback, useEffect, useRef, useState } from "react";

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
const DISMISS_THRESHOLD = 0.4;

/**
 * Resolve whether the user prefers reduced motion.
 * Exported for testing.
 */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export interface DragHandleProps {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: () => void;
}

export interface BottomSheetReturn {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  sheetRef: React.RefObject<HTMLDivElement | null>;
  dragHandleProps: DragHandleProps;
  sheetStyle: React.CSSProperties | undefined;
}

/**
 * Hook for a mobile bottom sheet with drag-to-dismiss, focus trap,
 * body scroll lock, and escape-to-close.
 */
export function useBottomSheet(): BottomSheetReturn {
  const [isOpen, setIsOpen] = useState(false);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<Element | null>(null);
  const dragStartYRef = useRef<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  const open = useCallback(() => {
    previousFocusRef.current = document.activeElement;
    setIsOpen(true);
    setDragOffset(0);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setDragOffset(0);
    (previousFocusRef.current as HTMLElement | null)?.focus();
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

    const handler = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        close();
        return;
      }
      if (e.key === "Tab" && sheetRef.current) {
        const focusable = Array.from(
          sheetRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
        ).filter((el) => !el.hasAttribute("disabled"));
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
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragStartYRef.current = e.touches[0].clientY;
  }, []);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
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

  const dragHandleProps: DragHandleProps = {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
  };

  const sheetStyle: React.CSSProperties | undefined = dragOffset > 0
    ? { transform: `translateY(${dragOffset}px)`, transition: "none" }
    : undefined;

  return { isOpen, open, close, sheetRef, dragHandleProps, sheetStyle };
}
