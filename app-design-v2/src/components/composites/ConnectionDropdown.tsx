/*
 * ::::: by  Pooya Deperson 2025  <pooyadeperson@gmail.com> :::::
 *
 * 🧩 React Component: ConnectionDropdown
 *
 * 📘 PURPOSE:
 *     Provides a dropdown interface for managing multiple connection states
 *     (e.g., Python server, WebSocket). Each connection can be toggled
 *     between “Connect”, “Connecting…”, and “Connected” states.
 *
 * ⚙️ HOW TO USE (React):
 *     1. Import and render this component anywhere in your app where
 *        you need to monitor or control connection statuses.
 *
 *        ```jsx
 *        import { ConnectionDropdown } from "@/components/ConnectionDropdown";
 *
 *        function HeaderBar() {
 *          return (
 *            <div className="flex justify-end p-2">
 *              <ConnectionDropdown />
 *            </div>
 *          );
 *        }
 *        ```
 *
 *     2. The component internally simulates a connection flow:
 *        - When you click “Connect”, it shows “Connecting…” for 2 seconds,
 *          then changes to “Connected”.
 *        - Clicking “Disconnect” resets the state to “Disconnected”.
 *
 * 🧠 BEHAVIOR:
 *     - The dropdown button text and icon reflect the overall system status:
 *         ✅ "Connected" if all are connected
 *         ⚙️ "Connecting..." if any are connecting
 *         ⚠️ "Not Connected" if all are disconnected
 *     - Each connection type (e.g., Python / WebSocket) is listed inside
 *       the dropdown with its current status and toggle button.
 *     - You can customize or extend supported connection types by editing
 *       the `connectionTypes` array or the `initialConnections` object.
 *
 * 🧩 DEPENDENCIES:
 *     - `DropdownButton` — UI wrapper for the dropdown trigger and content.
 *     - `ToggleButtonComponent` — Button component handling connect/disconnect logic.
 *
 * 💡 CUSTOMIZATION:
 *     - Adjust connection simulation timing in `handleConnect()`.
 *     - Replace icons (`connected-icon`, `loader-icon`, `warning-icon`) with
 *       your preferred icon classes or components.
 *     - Integrate with real connection APIs by replacing the `setTimeout`
 *       logic with actual async connection calls.
 */

import React, { useState } from "react";
import DropdownButton from "../uicomponents/DropdownButton";
import ToggleButtonComponent from "../uicomponents/ToggleButtonComponent";

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
