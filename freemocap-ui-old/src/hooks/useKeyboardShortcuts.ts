// src/hooks/useKeyboardShortcuts.ts
import {useEffect} from "react";
import {useAppDispatch} from "@/store";
// import { localeToggled } from "@/store/slices/settings";
import {pauseUnpauseCameras} from "@/store/slices/cameras";

/**
 * Registers global keyboard shortcuts that should be active app-wide.
 *
 *   Ctrl+Shift+L  — toggle between the current locale and the previous one
 *   Shift+Space   — pause / unpause camera streaming
 */
export function useKeyboardShortcuts(): void {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      // Ignore keystrokes aimed at text inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      // Ctrl+Shift+L (or Cmd+Shift+L on macOS) — toggle language
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        // dispatch(localeToggled());
        return;
      }

      // Shift+Space — pause / unpause camera streaming
      if (e.shiftKey && e.key === " ") {
        e.preventDefault();
        dispatch(pauseUnpauseCameras());
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dispatch]);
}
