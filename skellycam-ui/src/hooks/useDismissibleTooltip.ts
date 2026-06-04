import { useState, useCallback } from "react";

export function useDismissibleTooltip(storageKey: string) {
  const [isOpen, setIsOpen] = useState(
    () => localStorage.getItem(storageKey) !== "true",
  );

  const dismiss = useCallback(() => {
    localStorage.setItem(storageKey, "true");
    setIsOpen(false);
  }, [storageKey]);

  const open = useCallback(() => setIsOpen(true), []);

  return [isOpen, open, dismiss] as const;
}
