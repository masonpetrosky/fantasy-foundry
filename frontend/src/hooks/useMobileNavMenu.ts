import { useEffect, useRef, useState } from "react";
import { useMenuInteractions } from "../accessibility_components";

interface UseMobileNavMenuReturn {
  mobileNavOpen: boolean;
  setMobileNavOpen: React.Dispatch<React.SetStateAction<boolean>>;
  mobileNavMenuRef: React.RefObject<HTMLDivElement | null>;
  mobileNavTriggerRef: React.RefObject<HTMLButtonElement | null>;
}

export function useMobileNavMenu({ section }: { section: string }): UseMobileNavMenuReturn {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useMenuInteractions({ open, setOpen, menuRef, triggerRef });

  useEffect(() => {
    setOpen(false);
  }, [section]);

  return { mobileNavOpen: open, setMobileNavOpen: setOpen, mobileNavMenuRef: menuRef, mobileNavTriggerRef: triggerRef };
}
