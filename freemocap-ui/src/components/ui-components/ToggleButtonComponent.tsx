import React from "react";
import clsx from "clsx";
import { STATES } from "./states";

interface ToggleButtonComponentProps {
  state: string;
  connectConfig: { text: string; iconClass?: string; rightSideIcon?: string; extraClasses?: string };
  connectingConfig: { text: string; iconClass?: string; rightSideIcon?: string; extraClasses?: string };
  connectedConfig: { text: string; iconClass?: string; rightSideIcon?: string; extraClasses?: string };
  textColor?: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

const ToggleButtonComponent: React.FC<ToggleButtonComponentProps> = ({
  state,
  connectConfig,
  connectingConfig,
  connectedConfig,
  textColor = "text-gray",
  onConnect = () => {},
  onDisconnect = () => {},
}) => {
  const handleClick = () => {
    if (state === STATES.DISCONNECTED) onConnect();
    else if (state === STATES.CONNECTED) onDisconnect();
  };

  const getButtonConfig = () => {
    switch (state) {
      case STATES.CONNECTING: return connectingConfig;
      case STATES.CONNECTED: return connectedConfig;
      default: return connectConfig;
    }
  };

  const { text, iconClass, rightSideIcon, extraClasses } = getButtonConfig();

  return (
    <button
      onClick={handleClick}
      disabled={state === STATES.CONNECTING}
      className={clsx("gap-1 br-1 button sm fit-content flex-inline text-left items-center", extraClasses)}
    >
      {iconClass && <span className={`icon icon-size-20 ${iconClass}`} />}
      <p className={`${textColor} text md text-align-left`}>{text}</p>
      {rightSideIcon && <span className={`icon icon-size-20 ${rightSideIcon}`} />}
    </button>
  );
};

export default ToggleButtonComponent;
