import React from "react";
import clsx from "clsx";
import { TooltipPosition } from "./types";

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
  textClass?: string;
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
  textClass = "",
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
}) => {
  const innerContent = (
    <>
      {iconClass && <span className={clsx("icon icon-size-20", iconClass)} />}
      <p className={clsx(textColor, "text-nowrap text bg text-align-left", textClass)}>
        {text}
      </p>
    </>
  );

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
        className={clsx("button-sm-group pos-rel fit-content flex-inline")}
        style={{ opacity: 0.5, cursor: "not-allowed" }}
      >
        <button
          disabled
          title={title}
          className={clsx("gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black", buttonType, rightSideIcon, className)}
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
      className={clsx("button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black", buttonType, rightSideIcon, className)}
    >
      {innerContent}
      {tooltipEl}
    </button>
  );
};

export default ButtonSm;
