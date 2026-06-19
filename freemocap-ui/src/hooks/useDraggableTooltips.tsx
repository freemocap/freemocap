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
      
      const computedPos = window.getComputedStyle(el).position;
      if (computedPos === "static") {
        el.style.position = "absolute";
      }
      
      // Ensure the element creates a stacking context for nested positioned elements
      el.style.willChange = "transform";
      
      // Establish transform origin and ensure proper context for nested fixed/absolute elements
      if (!el.style.transformOrigin) {
        el.style.transformOrigin = "0 0";
      }

      let isPointerDown = false;
      let dragging = false;
      let startPointerX = 0;
      let startPointerY = 0;
      let currentTranslateX = 0;
      let currentTranslateY = 0;
      let accumulatedTranslateX = 0;
      let accumulatedTranslateY = 0;
      let originalChildPositions: Map<HTMLElement, string> = new Map();
      let originalChildZIndexes: Map<HTMLElement, string> = new Map();

      const onPointerDown = (ev: PointerEvent): void => {
        if (ev.pointerType === "mouse" && ev.button !== 0) return;

        const target = ev.target as HTMLElement;
        if (target.closest("button, input, textarea, select, a")) return;

        isPointerDown = true;
        startPointerX = ev.pageX;
        startPointerY = ev.pageY;

        // Store the accumulated offset from previous drags
        accumulatedTranslateX = currentTranslateX;
        accumulatedTranslateY = currentTranslateY;

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

      const onPointerMove = (ev: PointerEvent): void => {
        if (!isPointerDown) return;

        const dx = ev.pageX - startPointerX;
        const dy = ev.pageY - startPointerY;

        if (!dragging && Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) {
          dragging = true;
          toggleUserSelect(false);
          el.style.zIndex = "";
          
          // Ensure parent has position context for nested elements
          if (window.getComputedStyle(el).position === "static") {
            el.style.position = "relative";
          }
        }

        if (dragging) {
          ev.preventDefault();

          // Apply new drag relative to the accumulated offset
          currentTranslateX = accumulatedTranslateX + dx;
          currentTranslateY = accumulatedTranslateY + dy;
          el.style.transform = `translate(${currentTranslateX}px, ${currentTranslateY}px)`;
        }
      };

      const onPointerUp = (): void => {
        if (dragging) {
          toggleUserSelect(true);
          
          // Restore original positioning of nested elements
          originalChildPositions.forEach((originalPos, child) => {
            child.style.position = originalPos;
          });
          originalChildZIndexes.forEach((originalZIndex, child) => {
            child.style.zIndex = originalZIndex;
          });
          
          // Clear the maps for the next drag
          originalChildPositions.clear();
          originalChildZIndexes.clear();
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
