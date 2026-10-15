import {type HTMLAttributes, useLayoutEffect, useRef} from 'react';

interface TooltipSurfaceProps extends HTMLAttributes<HTMLDivElement> {
    /** Interactive callouts are controlled by their owner; plain hints follow parent hover/focus. */
    open?: boolean;
    onDismiss?: () => void;
}

/** All tooltip chrome lives in the browser top layer, outside ancestor clipping
 * and stacking contexts, without changing DOM ownership or becoming modal.
 * [@mdnPopoverAPI]
 */
export default function TooltipSurface({open, onDismiss, className = '', children, ...props}: TooltipSurfaceProps) {
    const ref = useRef<HTMLDivElement>(null);
    const dismissRef = useRef(onDismiss);
    dismissRef.current = onDismiss;
    useLayoutEffect(() => {
        const element = ref.current;
        const anchor = element?.parentElement;
        if (!element || !anchor) return;
        let frame = 0;
        let disposed = false;
        let dismissed = false;
        let hovered = anchor.matches(':hover');
        const interactive = open !== undefined;
        const placement = className.match(/\bpos-(top|bottom|left|right)(?:-(left|right))?\b/);
        const preferred = placement?.[1] ?? 'bottom';
        const align = placement?.[2];
        const padding = 12, gap = 8;

        const position = () => {
            if (!element.matches(':popover-open')) return;
            const a = anchor.getBoundingClientRect();
            const width = element.offsetWidth, height = element.offsetHeight;
            let side = preferred;
            const space = {top: a.top, bottom: innerHeight - a.bottom, left: a.left, right: innerWidth - a.right};
            const opposite = {top: 'bottom', bottom: 'top', left: 'right', right: 'left'} as const;
            const needed = (side === 'left' || side === 'right' ? width : height) + gap + padding;
            const other = opposite[side as keyof typeof opposite];
            if (space[side as keyof typeof space] < needed && space[other] > space[side as keyof typeof space]) side = other;
            let left = a.left + (a.width - width) / 2;
            let top = a.top + (a.height - height) / 2;
            if (side === 'left') left = a.left - width - gap;
            else if (side === 'right') left = a.right + gap;
            else {
                top = side === 'top' ? a.top - height - gap : a.bottom + gap;
                if (align === 'left') left = a.left;
                if (align === 'right') left = a.right - width;
            }
            // Pinned callouts use the shared drag hook's individual translate property.
            const [dragX = 0, dragY = 0] = element.style.translate.split(' ').map(value => parseFloat(value) || 0);
            left = Math.max(padding, Math.min(left + dragX, innerWidth - width - padding)) - dragX;
            top = Math.max(padding, Math.min(top + dragY, innerHeight - height - padding)) - dragY;
            left = Math.round(left * 100) / 100;
            top = Math.round(top * 100) / 100;
            // Only write changed values: FloatingOnboarding observes style mutations.
            if (element.style.left !== `${left}px`) element.style.left = `${left}px`;
            if (element.style.top !== `${top}px`) element.style.top = `${top}px`;
            frame = requestAnimationFrame(position);
        };
        const hide = () => {
            cancelAnimationFrame(frame);
            if (element.matches(':popover-open')) element.hidePopover();
        };
        const show = () => {
            if (disposed || dismissed || !element.isConnected || element.matches(':popover-open')) return;
            element.showPopover();
            position();
        };
        const sync = () => {
            if (interactive) {if (open) show(); else hide();}
            else if (hovered || anchor.matches(':focus-within')) show();
            else {dismissed = false; hide();}
        };
        const escape = (event: KeyboardEvent) => {
            if (event.key !== 'Escape' || !element.matches(':popover-open')) return;
            dismissed = true;
            hide();
            dismissRef.current?.();
        };
        const focusOut = () => queueMicrotask(sync);
        const enter = () => {hovered = true; sync();};
        const leave = () => {hovered = false; sync();};
        anchor.addEventListener('mouseenter', enter);
        anchor.addEventListener('mouseleave', leave);
        anchor.addEventListener('focusin', sync);
        anchor.addEventListener('focusout', focusOut);
        document.addEventListener('keydown', escape);
        sync();
        return () => {
            disposed = true;
            hide();
            anchor.removeEventListener('mouseenter', enter);
            anchor.removeEventListener('mouseleave', leave);
            anchor.removeEventListener('focusin', sync);
            anchor.removeEventListener('focusout', focusOut);
            document.removeEventListener('keydown', escape);
        };
    }, [open, className]);

    return <div {...props} ref={ref} popover="manual" role={props.role ?? (open === undefined ? 'tooltip' : undefined)}
        className={`${className} tooltip-surface`} style={{...props.style, position: 'fixed', inset: 'auto', margin: 0, transform: 'none'}}>
        {children}
    </div>;
}
