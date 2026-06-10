import React from "react";
import clsx from "clsx";
import { TooltipPosition } from "./types";

interface IconButtonProps {
  icon: string;
  onClick?: () => void;
  onMouseDown?: (e: React.MouseEvent) => void;
  disabled?: boolean;
  title?: string;
  className?: string;
  iconSize?: string;
  tooltip?: boolean;
  tooltipText?: string;
  tooltipPosition?: TooltipPosition;
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(({
  icon,
  onClick = () => {},
  onMouseDown,
  disabled = false,
  title,
  className = "icon-size-25",
  iconSize = "icon-size-20",
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
}, ref) => {
  const iconEl = <span className={clsx("icon", icon, iconSize)} />;

  const tooltipEl = tooltip && tooltipText && (
    <div className={clsx("tooltip-container elevated-sharp", tooltipPosition, "p-01 br-2 bg-dark")}>
      <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
        <p className="text-white text md">{tooltipText}</p>
      </div>
    </div>
  );

  if (disabled && tooltip && tooltipText) {
    return (
      <div
        className="tooltip-wrapper pos-rel"
        title={title}
        style={{ opacity: 0.5, cursor: "not-allowed", display: "inline-flex" }}
      >
        <button
          ref={ref}
          disabled
          onMouseDown={onMouseDown}
          className={clsx("button icon-button pos-rel br-1", className)}
          style={{ pointerEvents: "none" }}
        >
          {iconEl}
        </button>
        {tooltipEl}
      </div>
    );
  }

  return (
    <button
      ref={ref}
      onClick={onClick}
      onMouseDown={onMouseDown}
      disabled={disabled}
      title={title}
      className={clsx("button icon-button pos-rel br-1", className)}
    >
      {iconEl}
      {tooltipEl}
    </button>
  );
});

IconButton.displayName = "IconButton";

export default IconButton;
