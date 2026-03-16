import React, { createContext, useContext, useMemo } from "react";
import { useToast, type ToastEntry } from "./hooks/useToast";

interface ToastContextValue {
  toasts: ToastEntry[];
  addToast: (message: string, options?: { type?: "success" | "error" | "info"; duration?: number }) => number;
  dismissToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToastContext(): ToastContextValue | null {
  return useContext(ToastContext);
}

interface ToastProviderProps {
  children: React.ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps): React.ReactElement {
  const toast = useToast();
  const contextValue = useMemo(
    () => ({ toasts: toast.toasts, addToast: toast.addToast, dismissToast: toast.dismissToast }),
    [toast.toasts, toast.addToast, toast.dismissToast],
  );
  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismissToast} />
    </ToastContext.Provider>
  );
}

interface ToastContainerProps {
  toasts: ToastEntry[];
  onDismiss: (id: number) => void;
}

function ToastContainer({ toasts, onDismiss }: ToastContainerProps): React.ReactElement | null {
  if (toasts.length === 0) return null;
  return (
    <div className="toast-container" aria-live="polite" aria-relevant="additions">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`} role="status">
          <span className="toast-message">{t.message}</span>
          <button
            type="button"
            className="toast-dismiss"
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}
