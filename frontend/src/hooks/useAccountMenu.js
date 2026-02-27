import { useEffect, useRef, useState } from "react";
import { useMenuInteractions } from "../accessibility_components";

export function useAccountMenu({ section }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  useMenuInteractions({ open, setOpen, menuRef, triggerRef });

  useEffect(() => {
    setOpen(false);
  }, [section]);

  return { accountMenuOpen: open, setAccountMenuOpen: setOpen, accountMenuRef: menuRef, accountTriggerRef: triggerRef };
}
