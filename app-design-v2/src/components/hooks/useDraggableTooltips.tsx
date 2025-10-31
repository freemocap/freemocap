/*
 *     ::::: by  Pooya Deperson 2025  <pooyadeperson@gmail.com> :::::
 *
 * 🔧 React Hook: useDraggableTooltips
 *
 * 📘 PURPOSE:
 *     This hook enables draggable behavior for any DOM element
 *     that has the CSS class `.draggable`.
 *     It supports both mouse and touch input, prevents jumpy movement,
 *     and disables text selection while dragging for a smooth UX.
 *
 * 🚀 HOW TO USE (React):
 *     1. Save this file as: `src/hooks/useDraggableTooltips.ts` (or .js)
 *     2. Import and call the hook once in a component that mounts globally,
 *        such as App.tsx or a Layout component:
 *
 *        ```jsx
 *        import useDraggableTooltips from "@/hooks/useDraggableTooltips";
 *
 *        export default function App() {
 *          useDraggableTooltips(); // Activates draggable behavior globally
 *
 *          return (
 *            <div>
 *              <div className="draggable" style={{ position: "absolute", top: "100px", right: "100px" }}>
 *                Drag me around!
 *              </div>
 *            </div>
 *          );
 *        }
 *        ```
 *
 *     3. Any element with the `.draggable` class will automatically
 *        become movable on the screen.
 *
 * 🧩 NOTES:
 *     - The hook automatically observes newly added `.draggable` elements.
 *     - Elements with `position: static` are changed to `absolute` for proper movement.
 *     - Cursor changes between "grab" and "grabbing" while dragging.
 *     - For accessibility, avoid attaching `.draggable` to buttons or inputs directly.
 *
 * ✅ Example Styles (optional):
 *     .draggable {
 *       cursor: grab;
 *       user-select: none;
 *       touch-action: none;
 *     }
 */
import { useEffect } from "react";

export default function useDraggableTooltips(): void {
  useEffect(() => {
    const DRAG_THRESHOLD = 4; // px before drag starts

    const toggleUserSelect = (on: boolean): void => {
      document.documentElement.style.userSelect = on ? "" : "none";
    };

    const makeDraggable = (el: HTMLElement): void => {
      if ((el as any).__draggable_installed) return;
      (el as any).__draggable_installed = true;

      el.style.touchAction = "none";
      el.style.cursor = "grab";
      if (window.getComputedStyle(el).position === "static") {
        el.style.position = "absolute";
      }

      let isPointerDown = false;
      let dragging = false;
      let startPointerX = 0;
      let startPointerY = 0;
      let startTop = 0;
      let startRight = 0;

      const getNumeric = (v: string): number => parseFloat(v || "0") || 0;

      const onPointerDown = (ev: PointerEvent): void => {
        if (ev.pointerType === "mouse" && ev.button !== 0) return;

        const target = ev.target as HTMLElement;
        if (target.closest("button, input, textarea, select, a")) return;

        isPointerDown = true;
        startPointerX = ev.pageX;
        startPointerY = ev.pageY;

        // 👇 Compute actual on-screen position to avoid jump
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        // Use either explicit top/right, or compute from viewport
        const currentTop =
          style.top === "auto" || style.top === ""
            ? rect.top + window.scrollY
            : getNumeric(style.top);

        const currentRight =
          style.right === "auto" || style.right === ""
            ? window.innerWidth - (rect.right + window.scrollX)
            : getNumeric(style.right);

        startTop = currentTop;
        startRight = currentRight;

        // Visually indicate active grab
        el.style.cursor = "grabbing";
      };

      const onPointerMove = (ev: PointerEvent): void => {
        if (!isPointerDown) return;

        const dx = ev.pageX - startPointerX;
        const dy = ev.pageY - startPointerY;

        if (!dragging && Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) {
          dragging = true;
          toggleUserSelect(false);
          el.style.zIndex = "9999";
        }

        if (dragging) {
          ev.preventDefault();
          el.style.top = `${startTop + dy}px`;
          el.style.right = `${startRight - dx}px`;
        }
      };

      const onPointerUp = (): void => {
        if (dragging) {
          toggleUserSelect(true);
        }
        isPointerDown = false;
        dragging = false;
        el.style.cursor = "grab";
      };

      el.addEventListener("pointerdown", onPointerDown);
      window.addEventListener("pointermove", onPointerMove, { passive: false });
      window.addEventListener("pointerup", onPointerUp);
    };

    // Initialize all existing draggable elements
    document.querySelectorAll<HTMLElement>(".draggable").forEach(makeDraggable);

    // Observe dynamically added draggable elements
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;
          if (node.classList.contains("draggable")) makeDraggable(node);
          node.querySelectorAll<HTMLElement>(".draggable").forEach(makeDraggable);
        }
      }
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });

    console.log("✅ Draggable tooltips enabled (no-jump version).");

    return () => {
      observer.disconnect();
      toggleUserSelect(true);
    };
  }, []);
}
