import { useEffect, useRef, useState } from "react";
import { useMenuInteractions } from "../accessibility_components";

interface UseAccountMenuInput {
  section: string;
}

interface UseAccountMenuReturn {
  accountMenuOpen: boolean;
  setAccountMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  accountMenuRef: React.RefObject<HTMLDivElement | null>;
  accountTriggerRef: React.RefObject<HTMLButtonElement | null>;
}

export function useAccountMenu({ section }: UseAccountMenuInput): UseAccountMenuReturn {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useMenuInteractions({ open, setOpen, menuRef, triggerRef });

  useEffect(() => {
    setOpen(false);
  }, [section]);

  return { accountMenuOpen: open, setAccountMenuOpen: setOpen, accountMenuRef: menuRef, accountTriggerRef: triggerRef };
}
