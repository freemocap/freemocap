import React, { useState } from "react";
import clsx from "clsx";

interface ToggleProps {
  text: string;
  className?: string;
  iconClass?: string;
  defaultToggelState?: boolean;
  isToggled?: boolean;
  onToggle?: (state: boolean) => void;
  disabled?: boolean; // new prop
}

const ToggleComponent: React.FC<ToggleProps> = ({
  text,
  className = "",
  iconClass,
  defaultToggelState = false,
  isToggled,
  onToggle,
  disabled = false,
}) => {
  const [internalToggle, setInternalToggle] = useState(defaultToggelState);

  const toggled = isToggled !== undefined ? isToggled : internalToggle;

  const handleToggle = () => {
    if (disabled) return; // ignore clicks if disabled
    const newState = !toggled;
    if (isToggled === undefined) setInternalToggle(newState);
    onToggle?.(newState);
  };

  return (
    <div
      className={`button toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25 ${className} ${
        disabled ? "disabled" : ""
      }`}
      onClick={handleToggle}
    >
      <div className="text-container overflow-hidden flex items-center gap-1">
        {iconClass && (
          <span className={`icon icon-size-16 ${iconClass}`}></span>
        )}
        <p
          className={clsx(
            "text text-nowrap text-left md",
            toggled && "color-white"
          )}
        >
          {text}
        </p>
      </div>
      <div className={`icon toggle-container ${toggled ? "on" : "off"}`}>
        <div className="icon toggle-circle"></div>
      </div>
    </div>
  );
};

export default ToggleComponent;
