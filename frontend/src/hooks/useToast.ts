import { useCallback, useRef, useState } from "react";

let toastIdCounter = 0;

export type ToastType = "success" | "error" | "info";

export interface ToastEntry {
  id: number;
  message: string;
  type: ToastType;
}

export interface AddToastOptions {
  type?: ToastType;
  duration?: number;
}

export function useToast(): {
  toasts: ToastEntry[];
  addToast: (message: string, options?: AddToastOptions) => number;
  dismissToast: (id: number) => void;
} {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const timersRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  const dismissToast = useCallback((id: number) => {
    clearTimeout(timersRef.current[id]);
    delete timersRef.current[id];
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((message: string, { type = "info", duration }: AddToastOptions = {}) => {
    duration = duration ?? (type === "error" ? 0 : 3000);
    const id = ++toastIdCounter;
    setToasts(prev => [...prev.slice(-4), { id, message, type }]);
    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => dismissToast(id), duration);
    }
    return id;
  }, [dismissToast]);

  return { toasts, addToast, dismissToast };
}
