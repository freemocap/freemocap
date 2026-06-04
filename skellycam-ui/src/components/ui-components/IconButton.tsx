import React from "react";
import clsx from "clsx";
import { TooltipPosition } from "./types";

/**
 * =========================================
 * ICON BUTTON COMPONENT
 * =========================================
 *
 * Reusable icon-only button component with:
 *
 * - Dynamic icon support
 * - Click handling
 * - Disabled state
 * - Tooltip system
 * - Tooltip position support
 * - Custom className support
 *
 * -----------------------------------------
 * BASIC USAGE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="close-icon"
 *   onClick={onClose}
 * />
 *
 * -----------------------------------------
 * DIFFERENT ICONS
 * -----------------------------------------
 *
 * <IconButton
 *   icon="copyover-icon"
 * />
 *
 * <IconButton
 *   icon="trash-icon"
 * />
 *
 * -----------------------------------------
 * TOOLTIP USAGE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="copyover-icon"
 *   tooltip={true}
 *   tooltipText="Copy to clipboard"
 * />
 *
 * -----------------------------------------
 * TOOLTIP POSITIONS
 * -----------------------------------------
 *
 * - pos-bottom (default)
 * - pos-top
 * - pos-left
 * - pos-right
 *
 * -----------------------------------------
 * FULL EXAMPLE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="close-icon"
 *   onClick={onClose}
 *   tooltip={true}
 *   tooltipText="Close modal"
 *   tooltipPosition="pos-left"
 * />
 *
 * =========================================
 */


interface IconButtonProps {
  icon: string;
  onClick?: () => void;
  onMouseDown?: (e: React.MouseEvent) => void;
  disabled?: boolean;
  title?: string;
  className?: string;
  iconSize?: string;

  // TOOLTIP
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
  className = "icon-size-28",
  iconSize = "icon-size-20",

  // TOOLTIP
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
}, ref) => {
  const iconEl = (
    <span className={clsx("icon", icon, iconSize)} />
  );

  const tooltipEl = tooltip && tooltipText && (
    <div
      className={clsx(
        "tooltip-container elevated-sharp",
        tooltipPosition,
        "p-01 br-2 bg-dark"
      )}
    >
      <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
        <p className="text-white text md">{tooltipText}</p>
      </div>
    </div>
  );

  // When disabled with a tooltip, use a div wrapper so hover still fires.
  // button:disabled may suppress pointer events in some environments,
  // but the parent div reliably receives hover and shows the tooltip.
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
      className={clsx(
        "button icon-button pos-rel br-1",
        className
      )}
    >
      {iconEl}
      {tooltipEl}
    </button>
  );
});

export default IconButton;