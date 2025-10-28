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
