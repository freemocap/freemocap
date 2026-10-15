import React from "react";
import TooltipSurface from './TooltipSurface';
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
  const iconEl = <span className={clsx("icon", icon, iconSize)} style={iconStyle} />;

  const tooltipEl = tooltip && tooltipText && (
    <TooltipSurface className={clsx("tooltip-container elevated-sharp", tooltipPosition, "p-01 br-2 bg-dark")}>
      <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid"
        style={disabled ? {backgroundColor: "#20242a", borderColor: "#68717d"} : undefined}>
        <p className="text-white text md" style={disabled ? {color: "#ffffff"} : undefined}>{tooltipText}</p>
      </div>
    </TooltipSurface>
  );

  if (disabled && tooltip && tooltipText) {
    return (
      <div
        className="tooltip-wrapper icon-button pos-rel flex-inline"
        title={tooltipPortal ? undefined : title}
        style={{cursor: "not-allowed"}}
        tabIndex={0}
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

