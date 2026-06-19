/* *     ::::: by  Pooya Moradi M. 2025  <poamrd@gmail.com> :::::
 *
 * 🔧 React Hook: useDraggableTooltips
 *
 * 📘 PURPOSE:
 *     This hook enables draggable behavior for any DOM element
 *     that has the CSS class `.draggable`.
 *     It supports both mouse and touch input, prevents jumpy movement,
 *     and disables text selection while dragging for a smooth UX.
 *     Uses CSS transform for positioning, so it works with ANY positioning
 *     properties (left, right, top, bottom, or combinations).
 *     Properly handles nested components with fixed or absolute positioning.
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
 *              <div className="draggable" style={{ position: "absolute", top: "100px", left: "50px" }}>
 *                <div style={{ position: "fixed", top: 0, right: 0 }}>
 *                  This will move with the parent!
 *                </div>
 *                <div style={{ position: "absolute", bottom: 0 }}>
 *                  So will this!
 *                </div>
 *                Drag the parent around!
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
 *     - Uses `transform: translate()` internally, so it works with any combination
 *       of CSS positioning properties (left, right, top, bottom).
 *     - Inner components with position: fixed or absolute move correctly with the parent.
 *     - Fixed positioned nested elements are temporarily converted to absolute during drag
 *       to ensure they follow the parent element, then restored to fixed after dragging.
 *     - Nested absolute positioned elements maintain their relative positioning.
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

/** Per-element drag state. Kept in a Map keyed by the element so listeners and
 *  accumulated offsets can be cleaned up when the element leaves the DOM. */
interface DraggableState {
  pointerDownHandler: (ev: PointerEvent) => void;
  currentTranslateX: number;
  currentTranslateY: number;
}

export default function useDraggableTooltips(): void {
  useEffect(() => {
    const DRAG_THRESHOLD = 4; // px before drag starts

    const toggleUserSelect = (on: boolean): void => {
      document.documentElement.style.userSelect = on ? "" : "none";
    };

    // One state entry per registered `.draggable`. Replaces the old per-element
    // `__draggable_installed` marker + per-element window listeners (which were
    // never removed and leaked listeners + detached DOM nodes).
    const states = new Map<HTMLElement, DraggableState>();

    // Shared drag session — only one element can be dragged at a time, so the
    // window listeners below are installed ONCE and dispatch to `activeEl`.
    let activeEl: HTMLElement | null = null;
    let isPointerDown = false;
    let dragging = false;
    let startPointerX = 0;
    let startPointerY = 0;
    let accumulatedTranslateX = 0;
    let accumulatedTranslateY = 0;
    const originalChildPositions = new Map<HTMLElement, string>();
    const originalChildZIndexes = new Map<HTMLElement, string>();

    const onGlobalPointerMove = (ev: PointerEvent): void => {
      const el = activeEl;
      if (!isPointerDown || !el) return;
      const state = states.get(el);
      if (!state) return;

      const dx = ev.pageX - startPointerX;
      const dy = ev.pageY - startPointerY;

      if (!dragging && Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) {
        dragging = true;
        toggleUserSelect(false);
        el.style.zIndex = "9999";
        // Promote to its own layer only for the duration of the drag.
        el.style.willChange = "transform";

        // Ensure parent has position context for nested elements
        if (window.getComputedStyle(el).position === "static") {
          el.style.position = "relative";
        }
      }

      if (dragging) {
        ev.preventDefault();

        // Apply new drag relative to the accumulated offset
        state.currentTranslateX = accumulatedTranslateX + dx;
        state.currentTranslateY = accumulatedTranslateY + dy;
        el.style.transform = `translate(${state.currentTranslateX}px, ${state.currentTranslateY}px)`;
      }
    };

    const onGlobalPointerUp = (): void => {
      const el = activeEl;
      if (dragging && el) {
        toggleUserSelect(true);

        // Restore original positioning of nested elements
        originalChildPositions.forEach((originalPos, child) => {
          child.style.position = originalPos;
        });
        originalChildZIndexes.forEach((originalZIndex, child) => {
          child.style.zIndex = originalZIndex;
        });

        originalChildPositions.clear();
        originalChildZIndexes.clear();

        // Release the compositor layer now that the drag is done.
        el.style.willChange = "";
      }
      if (el) el.style.cursor = "grab";
      isPointerDown = false;
      dragging = false;
      activeEl = null;
    };

    const makeDraggable = (el: HTMLElement): void => {
      if (states.has(el)) return;

      el.style.touchAction = "none";
      el.style.cursor = "grab";

      const computedPos = window.getComputedStyle(el).position;
      if (computedPos === "static") {
        el.style.position = "absolute";
      }

      // Establish transform origin for nested fixed/absolute elements.
      if (!el.style.transformOrigin) {
        el.style.transformOrigin = "0 0";
      }

      const onPointerDown = (ev: PointerEvent): void => {
        if (ev.pointerType === "mouse" && ev.button !== 0) return;

        const target = ev.target as HTMLElement;
        if (target.closest("button, input, textarea, select, a")) return;

        const state = states.get(el);
        if (!state) return;

        activeEl = el;
        isPointerDown = true;
        dragging = false;
        startPointerX = ev.pageX;
        startPointerY = ev.pageY;

        // Store the accumulated offset from previous drags
        accumulatedTranslateX = state.currentTranslateX;
        accumulatedTranslateY = state.currentTranslateY;

        // Visually indicate active grab
        el.style.cursor = "grabbing";

        // Fix nested positioned elements before dragging starts
        const fixedElements = el.querySelectorAll<HTMLElement>("[style*='position: fixed'], [style*='position:fixed']");
        const absoluteElements = el.querySelectorAll<HTMLElement>("[style*='position: absolute'], [style*='position:absolute']");

        fixedElements.forEach((child) => {
          originalChildPositions.set(child, child.style.position);
          originalChildZIndexes.set(child, child.style.zIndex);
          child.style.position = "absolute";
          child.style.zIndex = "auto";
        });

        absoluteElements.forEach((child) => {
          originalChildZIndexes.set(child, child.style.zIndex);
          child.style.zIndex = "auto";
        });
      };

      el.addEventListener("pointerdown", onPointerDown);
      states.set(el, { pointerDownHandler: onPointerDown, currentTranslateX: 0, currentTranslateY: 0 });
    };

    const removeDraggable = (el: HTMLElement): void => {
      const state = states.get(el);
      if (!state) return;
      el.removeEventListener("pointerdown", state.pointerDownHandler);
      states.delete(el);
      // If the dragged element was just removed, end the session.
      if (activeEl === el) {
        activeEl = null;
        isPointerDown = false;
        dragging = false;
      }
    };

    // Single delegated window listener pair for the whole session.
    window.addEventListener("pointermove", onGlobalPointerMove, { passive: false });
    window.addEventListener("pointerup", onGlobalPointerUp);

    // Initialize all existing draggable elements
    document.querySelectorAll<HTMLElement>(".draggable").forEach(makeDraggable);

    // Observe dynamically added/removed draggable elements so per-element
    // listeners are torn down when a tooltip leaves the DOM.
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;
          if (node.classList.contains("draggable")) makeDraggable(node);
          node.querySelectorAll<HTMLElement>(".draggable").forEach(makeDraggable);
        }
        for (const node of m.removedNodes) {
          if (!(node instanceof HTMLElement)) continue;
          if (node.classList.contains("draggable")) removeDraggable(node);
          node.querySelectorAll<HTMLElement>(".draggable").forEach(removeDraggable);
        }
      }
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      window.removeEventListener("pointermove", onGlobalPointerMove);
      window.removeEventListener("pointerup", onGlobalPointerUp);
      for (const [el, state] of states) {
        el.removeEventListener("pointerdown", state.pointerDownHandler);
      }
      states.clear();
      toggleUserSelect(true);
    };
  }, []);
}
