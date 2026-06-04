import React from "react";
import clsx from "clsx";
import { TooltipPosition } from "./types";


/**
 * =========================================
 * BUTTON SM COMPONENT
 * =========================================
 *
 * Small reusable button component with:
 *
 * - Left icon support
 * - Custom button styles
 * - Right side icon classes
 * - Disabled state
 * - Tooltip system
 * - Tooltip position support
 * - Custom className extension
 *
 * -----------------------------------------
 * BASIC USAGE
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Save"
 * />
 *
 * -----------------------------------------
 * WITH ICON
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Delete"
 *   iconClass="icon-trash"
 * />
 *
 * -----------------------------------------
 * WITH CUSTOM BUTTON STYLE
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Primary"
 *   buttonType="btn-primary"
 * />
 *
 * -----------------------------------------
 * WITH CLICK EVENT
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Submit"
 *   onClick={handleSubmit}
 * />
 *
 * -----------------------------------------
 * DISABLED BUTTON
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Disabled"
 *   disabled={true}
 * />
 *
 * -----------------------------------------
 * TOOLTIP USAGE
 * -----------------------------------------
 *
 * Enable tooltip:
 *
 * tooltip={true}
 *
 * Set tooltip text:
 *
 * tooltipText="Save changes"
 *
 * Set tooltip position:
 *
 * tooltipPosition="pos-top"
 *
 * Available positions:
 *
 * - pos-bottom (default)
 * - pos-top
 * - pos-left
 * - pos-right
 *
 * -----------------------------------------
 * FULL TOOLTIP EXAMPLE
 * -----------------------------------------
 *
 * <ButtonSm
 *   text="Delete"
 *   iconClass="icon-trash"
 *   tooltip={true}
 *   tooltipText="Delete this item permanently"
 *   tooltipPosition="pos-right"
 * />
 *
 * -----------------------------------------
 * TOOLTIP ANIMATIONS
 * -----------------------------------------
 *
 * pos-bottom -> slides down
 * pos-top    -> slides up
 * pos-left   -> slides left
 * pos-right  -> slides right
 *
 * -----------------------------------------
 * IMPORTANT
 * -----------------------------------------
 *
 * Required CSS:
 *
 * - .button-sm-group
 * - .tooltip-container
 * - .tooltip-inner
 * - .pos-top
 * - .pos-bottom
 * - .pos-left
 * - .pos-right
 *
 * The button root already contains:
 *
 * className="button-sm-group"
 *
 * so no wrapper div is needed.
 *
 * -----------------------------------------
 * CUSTOMIZATION
 * -----------------------------------------
 *
 * Developers can fully customize:
 *
 * - colors
 * - borders
 * - animations
 * - tooltip spacing
 * - typography
 * - icon sizes
 * - tooltip arrow sizes
 *
 * using external CSS utility classes.
 *
 * =========================================
 */




interface ButtonSmProps {
  iconClass?: string;
  buttonType?: string;
  text: string;
  onClick?: () => void;
  rightSideIcon?: string;
  textColor?: string;
  title?: string;
  disabled?: boolean;
  className?: string;
  
   // // add extra text className prop for more customization
  textClass?: string;
  
  // TOOLTIP
  tooltip?: boolean;
  tooltipText?: string;
  tooltipPosition?: TooltipPosition;
}

const ButtonSm: React.FC<ButtonSmProps> = ({
  iconClass = "",
  buttonType = "",
  text,
  onClick = () => {},
  rightSideIcon = "",
  textColor = "text-gray",
  title,
  disabled = false,
  className = "",
    // add extra text className prop for more customization
  textClass = "",
  // TOOLTIP
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
}) => {
  const innerContent = (
    <>
      {/* LEFT ICON */}
      {iconClass && (
        <span className={clsx("icon icon-size-20", iconClass)} />
      )}

      {/* TEXT */}
      <p className={clsx(
        textColor,
        "text-nowrap text md text-align-left",
        textClass
      )}>
        {text}
      </p>
    </>
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
        className={clsx("button-sm-group pos-rel fit-content flex-inline")}
        style={{ opacity: 0.5, cursor: "not-allowed" }}
      >
        <button
          disabled
          title={title}
          className={clsx(
            "gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black",
            buttonType,
            rightSideIcon,
            className
          )}
          style={{ pointerEvents: "none" }}
        >
          {innerContent}
        </button>
        {tooltipEl}
      </div>
    );
  }

  return (
    <button
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={clsx(
        "button-sm-group",
        "gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black",
        buttonType,
        rightSideIcon,
        className
      )}
    >
      {innerContent}
      {tooltipEl}
    </button>
  );
};

export default ButtonSm;  