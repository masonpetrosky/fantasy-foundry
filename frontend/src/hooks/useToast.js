import { useCallback, useRef, useState } from "react";

let toastIdCounter = 0;

/**
 * Lightweight toast notification hook.
 * Returns { toasts, addToast, dismissToast }.
 *
 * addToast(message, { type?, duration? }) adds a toast.
 * type: "success" | "error" | "info" (default "info")
 * duration: auto-dismiss ms (default 3000, 0 = sticky)
 */
export function useToast() {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const dismissToast = useCallback((id) => {
    clearTimeout(timersRef.current[id]);
    delete timersRef.current[id];
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((message, { type = "info", duration = 3000 } = {}) => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev.slice(-4), { id, message, type }]);
    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => dismissToast(id), duration);
    }
    return id;
  }, [dismissToast]);

  return { toasts, addToast, dismissToast };
}
