import React, { useState } from "react";
import { DropdownButton, ToggleButtonComponent } from "./uicomponents";

const STATES = {
  DISCONNECTED: "disconnected",
  CONNECTING: "connecting",
  CONNECTED: "connected",
} as const;

type ConnectionType = keyof typeof initialConnections;

const initialConnections = {
  python: STATES.DISCONNECTED,
  websocket: STATES.DISCONNECTED,
};

export function ConnectionDropdown() {
  const [connections, setConnections] = useState(initialConnections);

  const handleConnect = (type: ConnectionType) => {
    setConnections((prev) => ({ ...prev, [type]: STATES.CONNECTING }));
    setTimeout(() => {
      setConnections((prev) => ({ ...prev, [type]: STATES.CONNECTED }));
    }, 2000);
  };

  const handleDisconnect = (type: ConnectionType) => {
    setConnections((prev) => ({ ...prev, [type]: STATES.DISCONNECTED }));
  };

  const getToggleConfig = (state: string) => {
    switch (state) {
      case STATES.CONNECTING:
        return { text: "Connecting...", extraClasses: "loading disabled" };
      case STATES.CONNECTED:
        return { text: "Connected", extraClasses: "activated" };
      default:
        return { text: "Connect", extraClasses: "" };
    }
  };

  const getStatusIcon = (state: string) => {
    switch (state) {
      case STATES.CONNECTED:
        return "connected-icon";
      case STATES.CONNECTING:
        return "loader-icon";
      default:
        return "warning-icon";
    }
  };

  const connectionTypes = [
    { key: "python" as ConnectionType, label: "Python server" },
    { key: "websocket" as ConnectionType, label: "Websocket" },
  ];

  const getDropdownButtonState = () => {
    const states = Object.values(connections);
    if (states.every((s) => s === STATES.CONNECTED)) return { text: "Connected", iconClass: "connected-icon" };
    if (states.some((s) => s === STATES.CONNECTING)) return { text: "Connecting...", iconClass: "loader-icon" };
    if (states.some((s) => s === STATES.CONNECTED)) return { text: "Partially Connected", iconClass: "connected-icon" };
    return { text: "Not Connected", iconClass: "warning-icon" };
  };

  const dropdownButtonState = getDropdownButtonState();

  return (
    <DropdownButton
      buttonProps={{
        text: dropdownButtonState.text,
        iconClass: dropdownButtonState.iconClass,
        rightSideIcon: "dropdown",
        textColor: "text-gray",
      }}
      dropdownItems={
        <div className="connection-container flex flex-col p-1 gap-1 br-1 bg-darkgray border-1 border-mid-black">
          {connectionTypes.map(({ key, label }) => (
            <div
              key={key}
              className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25"
            >
              <div className="text-container overflow-hidden flex items-center gap-1">
                <span className={`icon icon-size-16 ${getStatusIcon(connections[key])}`}></span>
                <p className="text text-nowrap text-left bg">{label}</p>
              </div>

              <ToggleButtonComponent
                state={connections[key]}
                STATES={STATES}
                connectConfig={getToggleConfig(STATES.DISCONNECTED)}
                connectingConfig={getToggleConfig(STATES.CONNECTING)}
                connectedConfig={getToggleConfig(STATES.CONNECTED)}
                textColor="text-white"
                onConnect={() => handleConnect(key)}
                onDisconnect={() => handleDisconnect(key)}
              />
            </div>
          ))}
          <div className="flex flex-row p-1 gap-1">
            <p className="text-left text">
              Having trouble connecting? Learn how to connect...
            </p>
          </div>
        </div>
      }
    />
  );
}
