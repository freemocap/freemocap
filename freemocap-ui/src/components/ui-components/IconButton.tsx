import React, {useEffect, useState} from "react";
import {createPortal} from "react-dom";
import clsx from "clsx";
import { TooltipPosition } from "./ui-component-types";

interface IconButtonProps {
  icon: string;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  onMouseDown?: (e: React.MouseEvent) => void;
  disabled?: boolean;
  title?: string;
  ariaLabel?: string;
  className?: string;
  iconSize?: string;
  style?: React.CSSProperties;
  iconStyle?: React.CSSProperties;
  tooltip?: boolean;
  tooltipText?: string;
  tooltipPosition?: TooltipPosition;
  tooltipPortal?: boolean;
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(({
  icon,
  onClick = () => {},
  onMouseDown,
  disabled = false,
  title,
  ariaLabel,
  className = "icon-size-25",
  iconSize = "icon-size-20",
  style,
  iconStyle,
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
  tooltipPortal = false,
}, ref) => {
  const [tooltipAnchor, setTooltipAnchor] = useState<DOMRect | null>(null);
  useEffect(() => {
    if (!tooltipAnchor) return;
    const dismiss = () => setTooltipAnchor(null);
    window.addEventListener('scroll', dismiss, true);
    window.addEventListener('resize', dismiss);
    return () => {
      window.removeEventListener('scroll', dismiss, true);
      window.removeEventListener('resize', dismiss);
    };
  }, [tooltipAnchor]);
  const iconEl = <span className={clsx("icon", icon, iconSize)} style={iconStyle} />;

  const tooltipEl = tooltipPortal
    ? tooltip && tooltipText && tooltipAnchor && createPortal(
      <div role="tooltip" style={{position: 'fixed', zIndex: 2147483647,
        left: Math.max(12, Math.min(tooltipAnchor.left + tooltipAnchor.width / 2 - 210, window.innerWidth - 432)),
        top: tooltipAnchor.top - 8, transform: 'translateY(-100%)',
        width: 'max-content', maxWidth: 'min(420px, calc(100vw - 24px))',
        padding: '6px 10px', borderRadius: 4, border: '1px solid #68717d',
        background: '#20242a', color: '#fff', fontSize: 13, lineHeight: 1.4,
        boxShadow: '0 2px 8px #0008', pointerEvents: 'none'}}>{tooltipText}</div>, document.body)
    : tooltip && tooltipText && (
    <div className={clsx("tooltip-container elevated-sharp", tooltipPosition, "p-01 br-2 bg-dark")}>
      <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid"
        style={disabled ? {backgroundColor: "#20242a", borderColor: "#68717d"} : undefined}>
        <p className="text-white text md" style={disabled ? {color: "#ffffff"} : undefined}>{tooltipText}</p>
      </div>
    </div>
  );

  if (disabled && tooltip && tooltipText) {
    return (
      <div
        className="tooltip-wrapper icon-button pos-rel flex-inline"
        title={tooltipPortal ? undefined : title}
        style={{ zIndex: 10000, cursor: "not-allowed" }}
        onMouseEnter={event => {if (tooltipPortal) setTooltipAnchor(event.currentTarget.getBoundingClientRect());}}
        onMouseLeave={() => setTooltipAnchor(null)}
      >
        <button
          aria-label={ariaLabel}
      ref={ref}
          disabled
          onMouseDown={onMouseDown}
          className={clsx("button icon-button icon-size-25 pos-rel br-1", className)}
          style={{ ...style, opacity: 0.5, pointerEvents: "none" }}
        >
          {iconEl}
        </button>
        {tooltipEl}
      </div>
    );
  }

  return (
    <button
      aria-label={ariaLabel}
      ref={ref}
      onClick={onClick}
      onMouseEnter={event => {if (tooltipPortal) setTooltipAnchor(event.currentTarget.getBoundingClientRect());}}
      onMouseLeave={() => setTooltipAnchor(null)}
      onFocus={event => {if (tooltipPortal) setTooltipAnchor(event.currentTarget.getBoundingClientRect());}}
      onBlur={() => setTooltipAnchor(null)}
      onMouseDown={onMouseDown}
      disabled={disabled}
      title={tooltipPortal ? undefined : title}
      className={clsx("button icon-button pos-rel br-1", className)}
      style={style}
    >
      {iconEl}
      {tooltipEl}
    </button>
  );
});

IconButton.displayName = "IconButton";

export default IconButton;

