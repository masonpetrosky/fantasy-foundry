import { useEffect, useRef } from "react";

/**
 * Returns a ref to attach to a heading element.  On first mount the element
 * receives focus so screen-reader users are oriented after a lazy route loads.
 *
 * The element should have `tabIndex={-1}` so it is focusable but not part of
 * the normal tab order.
 */
export function useFocusOnMount<T extends HTMLElement = HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);
  return ref;
}
