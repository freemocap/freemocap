// src/hooks/useKeyboardShortcuts.ts
import { useEffect } from "react";
import { useAppDispatch } from "@/store";
import { localeToggled } from "@/store/slices/settings";
import { pauseUnpauseCameras } from "@/store/slices/cameras";
import { useRecordingGuard } from "@/components/RecordingGuardProvider";

/**
 * Registers global keyboard shortcuts that should be active app-wide.
 *
 *   Ctrl+Shift+L  — toggle between the current locale and the previous one
 *   Shift+Space   — pause / unpause camera streaming
 */
export function useKeyboardShortcuts(): void {
  const dispatch = useAppDispatch();
  const { requestGuardedAction } = useRecordingGuard();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      // Ignore keystrokes aimed at text inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      // Ctrl/Cmd+R and F5 — disabled; reload kills the Python server
      if (((e.ctrlKey || e.metaKey) && (e.key === "r" || e.key === "R")) || e.key === "F5") {
        e.preventDefault();
        return;
      }

      // Ctrl+Shift+L (or Cmd+Shift+L on macOS) — toggle language
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        dispatch(localeToggled());
        return;
      }

      // Shift+Space — pause / unpause camera streaming
      if (e.shiftKey && e.key === " ") {
        e.preventDefault();
        requestGuardedAction('Stop Recording & Pause Cameras', () => dispatch(pauseUnpauseCameras()));
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dispatch, requestGuardedAction]);
}
