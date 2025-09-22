/* --- Dropdown wrapper with connection controls --- */
import { useAppSelector, type ServerStatus } from "@/store";

import DropdownButton from "@/components/composites/DropdownButton.tsx";


/* --- Connection states (enum-like) --- */
const STATES = {
  DISCONNECTED: "disconnected",
  CONNECTING: "connecting",
  CONNECTED: "connected",
};

/* --- Reusable Toggle Button --- */
const ToggleButtonComponent = ({
  state,
  connectConfig,
  connectingConfig,
  connectedConfig,
  textColor = "text-gray",
  onConnect = () => {},
  onDisconnect = () => {},
}) => {
  // Handle button clicks
  const handleClick = () => {
    if (state === STATES.DISCONNECTED) {
      onConnect(); // trigger connect
    } else if (state === STATES.CONNECTED) {
      onDisconnect(); // trigger disconnect
    }
  };

  // Get the right config based on current state
  const getButtonConfig = () => {
    switch (state) {
      case STATES.CONNECTING:
        return connectingConfig;
      case STATES.CONNECTED:
        return connectedConfig;
      default:
        return connectConfig;
    }
  };

  const { text, iconClass, rightSideIcon, extraClasses } = getButtonConfig();

  return (
    <button
      onClick={handleClick}
      disabled={state === STATES.CONNECTING}
      className={clsx(
        "gap-1 br-1 button sm flex-inline text-left items-center",
        extraClasses
      )}
    >
      {/* Optional left-side icon */}
      {iconClass && <span className={`icon icon-size-16 ${iconClass}`} />}
      <p className={`${textColor} text md text-align-left`}>{text}</p>
      {/* Optional right-side icon */}
      {rightSideIcon && (
        <span className={`icon icon-size-16 ${rightSideIcon}`} />
      )}
    </button>
  );
};

/* --- Dropdown wrapper with connection controls --- */
const ConnectionDropdown = () => {
  // Track the state of each connection independently
  const [connections, setConnections] = useState({
    python: STATES.DISCONNECTED,
    websocket: STATES.DISCONNECTED,
  });

  /* --- Handlers to connect / disconnect a given type --- */
  const handleConnect = (type) => {
    // Step 1: mark as "connecting"
    setConnections((prev) => ({ ...prev, [type]: STATES.CONNECTING }));

    // Step 2: simulate async connection with timeout
    // 👉 Replace this with REAL connection logic later
    setTimeout(() => {
      setConnections((prev) => ({ ...prev, [type]: STATES.CONNECTED }));
    }, 2000);
  };

  const handleDisconnect = (type) => {
    // 👉 Replace with real disconnect logic (close connection, cleanup)
    setConnections((prev) => ({ ...prev, [type]: STATES.DISCONNECTED }));
  };

  /* --- Config for the button label (without icons) --- */
  const getToggleConfig = (state) => {
    switch (state) {
      case STATES.CONNECTING:
        return {
          text: "Connecting...",
          extraClasses: "loading disabled",
        };
      case STATES.CONNECTED:
        return {
          text: "Connected",
          extraClasses: "activated",
        };
      default:
        return {
          text: "Connect",
          extraClasses: "",
        };
    }
  };

  /* --- Helper: get the correct status icon for a row --- */
  const getStatusIcon = (state) => {
    switch (state) {
      case STATES.CONNECTED:
        return "connected-icon";
      case STATES.CONNECTING:
        return "loader-icon";
      default:
        return "warning-icon";
    }
  };

  /* --- Types of connections we support --- */
  const connectionTypes = [
    { key: "python", label: "Python server" },
    { key: "websocket", label: "Websocket" },
  ];

  /* --- Dropdown button state depends on both connections --- */
  const getDropdownButtonState = () => {
    const states = Object.values(connections);

    if (states.every((s) => s === STATES.CONNECTED)) {
      // ✅ Both connected → just say "Connected"
      return { text: "Connected", iconClass: "connected-icon" };
    } else if (states.some((s) => s === STATES.CONNECTING)) {
      // 🔄 Any connecting → show "Connecting..."
      return { text: "Connecting...", iconClass: "loader-icon" };
    } else if (states.some((s) => s === STATES.CONNECTED)) {
      // ⚠️ At least one connected → "Partially Connected"
      return { text: "Partially Connected", iconClass: "connected-icon" };
    } else {
      // ❌ None connected
      return { text: "Not Connected", iconClass: "warning-icon" };
    }
  };

  const dropdownButtonState = getDropdownButtonState();

  return (
    <DropdownButton
      /* --- Dropdown main button (summary of all connections) --- */
      buttonProps={{
        text: dropdownButtonState.text,
        iconClass: dropdownButtonState.iconClass,
        rightSideIcon: "dropdown", // chevron arrow
        textColor: "text-gray",
      }}
      /* --- Dropdown content: list of connections --- */
      dropdownItems={
        <div className="connection-container flex flex-col p-1 gap-1 br-1 bg-darkgray border-1 border-mid-black">
          {connectionTypes.map(({ key, label }) => (
            <div
              key={key}
              className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25"
            >
              {/* Left side: status icon + label */}
              <div className="text-container overflow-hidden flex items-center gap-1">
                <span
                  className={`icon icon-size-16 ${getStatusIcon(
                    connections[key]
                  )}`}
                ></span>
                <p className="text text-nowrap text-left bg">{label}</p>
              </div>

              {/* Right side: individual toggle button */}
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

          {/* Footer info */}
          <div className="flex flex-row p-1 gap-1">
            <p className="text-left text">
              Having trouble connecting? Learn how to connect...
            </p>
          </div>
        </div>
      }
    />
  );
};

export {ConnectionDropdown};
