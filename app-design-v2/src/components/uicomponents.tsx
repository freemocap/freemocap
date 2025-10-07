import React, { useState, useEffect, useRef } from "react";
import clsx from "clsx";

// /**
//  * ToggleComponent
//  * --------------------
//  * A reusable toggle UI component with customizable text, icons, and styles.
//  * Clicking anywhere on the parent div toggles the state.
//  *
//  * Props:
//  * ------
//  * @param {string} text - The label displayed next to the toggle.
//  * @param {React.ReactNode} [iconOn] - Icon or element for the "on" state. Default: "✔️".
//  * @param {React.ReactNode} [iconOff] - Icon or element for the "off" state. Default: "❌".
//  * @param {string} [className] - Optional class for the parent wrapper to extend/override default styles.
//  * @param {string} [iconClass] - Optional class for the dropdown icon to style it independently.
//  *
//  * Usage Example:
//  * --------------
//  * import ToggleComponent from "./components/uicomponents/ToggleComponent";
//  *
//  * function App() {
//  *   return (
//  *     <div className="flex flex-col gap-4">
//  *
//  *       {/* Default toggle */}
//  *       <ToggleComponent text="Default Toggle" />
//  *
//  *       {/* Custom icons with additional parent class */}
//  *       <ToggleComponent
//  *         text="Green Toggle"
//  *         iconOn="🟢"
//  *         iconOff="⚪"
//  *         className="green-toggle"
//  *         iconClass="custom-dropdown-icon"
//  *       />
//  *
//  *       {/* Star icons with unique styling */}
//  *       <ToggleComponent
//  *         text="Stars Toggle"
//  *         iconOn="⭐"
//  *         iconOff="☆"
//  *         className="star-toggle"
//  *         iconClass="star-dropdown-icon"
//  *       />
//  *
//  *     </div>
//  *   );
//  * }
//  *
//  * Notes for Developers:
//  * ---------------------
//  * - The `className` prop lets you customize the parent container style.
//  * - `iconClass` lets you style the dropdown icon independently.
//  * - You can pass any ReactNode to `iconOn` and `iconOff` (emoji, SVG, or JSX elements).
//  * - Clicking anywhere on the parent div toggles the state by default.
//  * - Each toggle manages its own internal state; to control externally, you could refactor to accept `isToggled` and `onToggle` props.
//  */

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

interface SegmentedControlProps {
  /**
   * Array of options to display.
   */
  options: SegmentedControlOption[];
  /**
   * Default selected value (uncontrolled mode).
   */
  defaultValue?: string;
  /**
   * Callback when selection changes.
   */
  onChange?: (value: string) => void;
  /**
   * Additional class for the container.
   */
  className?: string;
  /**
   * Size of the text: "sm" for small, "md" for medium (default).
   */
  size?: "sm" | "md";
  /**
   * Optional value for controlled mode.
   */
  value?: string;
}

/**
 * SegmentedControl Component
 * --------------------------
 * A reusable segmented control (toggle button group) component.
 * Features:
 * - Toggle between options with active/idle states.
 * - Customizable labels, values, and icons.
 * - Callback for selection changes.
 * - Supports controlled and uncontrolled usage.
 * - Supports small and medium text sizes.
 *
 * Props:
 * ------
 * @param {SegmentedControlOption[]} options - Array of options to display.
 * @param {string} [defaultValue] - Default selected value (uncontrolled mode).
 * @param {(value: string) => void} [onChange] - Callback when selection changes.
 * @param {string} [className] - Additional class for the container.
 * @param {"sm" | "md"} [size] - Size of the text.
 * @param {string} [value] - Value for controlled mode.
 *
 * Usage Example:
 * --------------
 * import { SegmentedControl } from "./YourComponentFile";
 *
 * function App() {
 *   const [mode, setMode] = useState("live");
 *   return (
 *     <SegmentedControl
 *       options={[
 *         { label: "Live", value: "live" },
 *         { label: "Post", value: "post" },
 *       ]}
 *       size="sm"
 *       value={mode}
 *       onChange={setMode}
 *     />
 *   );
 * }
 *
 * Notes for Developers:
 * ---------------------
 * - For controlled usage, use `value` and `onChange`.
 * - For uncontrolled usage, use `defaultValue`.
 * - Customize the active/idle styling via CSS classes.
 */
const SegmentedControl: React.FC<SegmentedControlProps> = ({
  options,
  defaultValue,
  onChange,
  className = "",
  size = "md",
  value: controlledValue,
}) => {
  const isControlled = controlledValue !== undefined;
  const [activeValue, setActiveValue] = useState(
    isControlled ? controlledValue : defaultValue || options[0]?.value
  );

  useEffect(() => {
    if (isControlled && controlledValue !== activeValue) {
      setActiveValue(controlledValue);
    }
  }, [controlledValue, isControlled, activeValue]);

  const handleClick = (value: string) => {
    if (!isControlled) {
      setActiveValue(value);
    }
    if (onChange) onChange(value);
  };

  const textSizeClass = size === "sm" ? "sm" : "md";

  return (
    <div
      className={`segmented-control-container br-1-1 gap-1 p-1 bg-middark flex ${className}`}
    >
      {options.map((option) => (
        <button
          key={option.value}
          className={`segmented-control-button justify-center button gap-1 br-1 flex-inline items-center ${
            activeValue === option.value
              ? "active text-white bg-dark"
              : "idle text-gray"
          }`}
          onClick={() => handleClick(option.value)}
        >
          {option.iconClass && <i className={option.iconClass} />}
          <p className={`${textSizeClass} text text-center p-1`}>
            {option.label}
          </p>
        </button>
      ))}
    </div>
  );
};

// Example usage:
// --------------
// const [mode, setMode] = useState("live");
// <SegmentedControl
//   options={[
//     { label: "Live Capture", value: "live", iconClass: "live-icon" },
//     { label: "Post-process", value: "post", iconClass: "post-icon" },
//   ]}
//   defaultValue="live"
//   onChange={setMode}
// />

// PROPS for ButtonSm:
// - iconClass (string): class name for the icon (e.g., "live-icon").
// - text (string): the button label text.
// - onClick (function): the action to run when button is clicked.
//   If none is provided, it defaults to a no-op function.

const ButtonSm = ({
  iconClass = "", // left-side icon
  buttonType = "", // valid types are : use classes like this  // for primaruy use: primary full-width justify-center // for secondary use " secondary full-width justify-center ""
  text,
  onClick = () => {},
  rightSideIcon = "", // "externallink" | "dropdown" | ""
  textColor = "text-gray", // "text-gray" | "text-white"
}) => {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "gap-1 br-1 button sm fit-content flex-inline text-left items-center", // base styles
        buttonType, // multiple classes supported here
        rightSideIcon // this is being treated as classes, same as before
      )}
    >
      {/* LEFT ICON */}
      {iconClass && <span className={clsx("icon icon-size-16", iconClass)} />}

      {/* TEXT */}
      <p className={clsx(textColor, "text md text-align-left")}>{text}</p>
    </button>
  );
};

/**
 * Reusable Checkbox Component
 * ----------------------------
 * - Combines a native <input type="checkbox"> with a text label (<p> tag).
 * - Use the `label` prop to change the string next to the checkbox.
 * - `checked` + `onChange` make this component controllable from parent state.
 * - The entire container is clickable to toggle the checkbox.
 */

interface CheckboxProps {
  label: string; // text shown next to the checkbox (developers can change this freely)
  checked?: boolean; // optional controlled state
  onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void; // handler for state changes
}

const Checkbox: React.FC<CheckboxProps> = ({ label, checked, onChange }) => {
  return (
    <div
      className="text-nowrap button checkbox gap-1 flex flex-row items-center"
      onClick={(e) => {
        // Allow clicking anywhere on the container to toggle checkbox
        if (onChange) {
          onChange({
            ...e,
            target: { ...(e.target as HTMLInputElement), checked: !checked },
          } as React.ChangeEvent<HTMLInputElement>);
        }
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="button"
      />
      <p className="text-gray text sm text-align-left">{label}</p>
    </div>
  );
};

/**
 * ButtonCard Component
 * --------------------
 * A reusable UI component that displays a card-like button with:
 * - An icon (customizable via CSS class)
 * - A text label (string passed as a prop)
 * - A click handler (function passed as a prop)
 *
 * Props:
 * ------
 * @param {string} text - The text displayed under the icon.
 * @param {string} iconClass - The class(es) applied to the <span> element for styling the icon.
 * Example: "live-icon icon-size-42".
 * @param {function} onClick - The function triggered when the button is clicked.
 * @param {string} [className] - (Optional) Additional classes to extend/override the default wrapper styles.
 *
 * Usage Example:
 * --------------
 * import ButtonCard from "./ButtonCard";
 *
 * function App() {
 * const handleLiveClick = () => {
 * console.log("Capture Live button clicked!");
 * };
 *
 * return (
 * <div className="flex gap-4">
 * <ButtonCard
 * text="Capture Live"
 * iconClass="live-icon icon-size-42"
 * onClick={handleLiveClick}
 * />
 *
 * <ButtonCard
 * text="Upload File"
 * iconClass="upload-icon icon-size-42"
 * onClick={() => alert("Upload File clicked")}
 * className="bg-blue-600"
 * />
 * </div>
 * );
 * }
 *
 * Notes for Developers:
 * ---------------------
 * - The `iconClass` lets you swap out icons dynamically by just changing the class string.
 * - If you need SVG or inline icons, you can refactor to accept an `icon` ReactNode prop instead.
 * - The default styling is based on the original HTML snippet (dark background, flex, centered).
 * Override or extend using the optional `className` prop.
 */

const ButtonCard = ({ text, iconClass, onClick, className = "" }) => {
  return (
    <div
      className={`button items-center flex-col justify-content-space-between p-3 text-aligh-center button card bg-dark flex-1 br-2 flex items-center justify-center text-white text-xs ${className}`}
      onClick={onClick}
    >
      {/* Icon section - styled via passed classes */}
      <span className={`icon m-3 ${iconClass}`}></span>

      {/* Text section */}
      <p className="text-center text bg">{text}</p>
    </div>
  );
};

/* Dropdown button */

interface DropdownButtonProps {
  buttonProps: {
    text: string;
    iconClass?: string;
    rightSideIcon?: string;
    textColor?: string;
    buttonType?: string;
    onClick?: () => void; // optional, in addition to dropdown toggle
  };
  dropdownItems?: ReactNode; // any JSX to render inside dropdown
  containerClassName?: string; // NEW: optional classes for the container div
}

export default function DropdownButton({
  buttonProps,
  dropdownItems,
  containerClassName, // NEW: allow external classes
}: DropdownButtonProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleButtonClick = () => {
    // Toggle dropdown
    setOpen((prev) => !prev);
    // Run any additional onClick passed to the main button
    buttonProps.onClick?.();
  };

  return (
    <div
      ref={containerRef}
      // Default classes + any custom ones provided
      className={clsx("flex flex-col z-2", containerClassName)}
    >
      <ButtonSm
        {...buttonProps}
        onClick={handleButtonClick} // wraps dropdown toggle + optional extra onClick
      />

      {open && (
        <div
          className="reveal slide-down dropdown-container border-1 border-black bg-middark br-2 pos-abs flex flex-col gap-1 p-1"
          style={{ top: "33px" }}
        >
          {dropdownItems}
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------
USAGE EXAMPLES

1. Basic usage (same as before, default container styling):

<DropdownButton
  buttonProps={{ text: "Menu" }}
  dropdownItems={<div>Item 1</div>}
/>

2. Add custom styles to the container:

<DropdownButton
  buttonProps={{ text: "Menu" }}
  dropdownItems={<div>Item 1</div>}
  containerClassName="items-end bg-gray-800"
/>

➡ This will merge the default classes (flex flex-col z-2 align-end) with your
   provided classes (items-end bg-gray-800).

3. Advanced example with extra button props:

<DropdownButton
  buttonProps={{
    text: "Settings",
    iconClass: "icon-gear",
    textColor: "text-white",
    buttonType: "primary",
    onClick: () => console.log("Main button clicked"),
  }}
  dropdownItems={
    <>
      <div>Profile</div>
      <div>Logout</div>
    </>
  }
  containerClassName="w-48 border rounded shadow-lg"
/>

-------------------------------------------------------------------------- */

/* --- Connection states (enum-like) --- */
export const STATES = { // <-- ADD export
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
        "gap-1 br-1 button sm fit-content flex-inline text-left items-center",
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

/* --- Example: Standalone Toggle Usage --- */
// const StandaloneToggleExample = () => {
//   const [state, setState] = useState(STATES.DISCONNECTED);

//   return (
//     <ToggleButtonComponent
//       state={state}
//       connectConfig={{
//         text: "Stream Camera",
//         iconClass: "stream-icon",
//         rightSideIcon: "",
//         extraClasses: "",
//       }}
//       connectingConfig={{
//         text: "Checking...",
//         iconClass: "loader-icon",
//         rightSideIcon: "",
//         extraClasses: "loading disabled",
//       }}
//       connectedConfig={{
//         text: "Streaming",
//         iconClass: "streaming-icon",
//         rightSideIcon: "",
//         extraClasses: "activated",
//       }}
//       textColor="text-white"
//       onConnect={() => {
//         console.log("Checking before streaming…");
//         setState(STATES.CONNECTING);

//         // Simulate async check before streaming
//         setTimeout(() => {
//           console.log("Streaming started!");
//           setState(STATES.CONNECTED);
//         }, 2000);
//       }}
//       onDisconnect={() => {
//         console.log("Stopped streaming!");
//         setState(STATES.DISCONNECTED);
//       }}
//     />
//   );
// };

// Reusable InputWithUnit
const InputWithUnit = ({
  value,
  onChange,
  unit = "",
  placeholder = "",
  className = "",
  inputClassName = "",
  unitClassName = "",
  min = 1,
  max = 999,
  onEnter, // ✅ new prop
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onEnter?.();
      inputRef.current?.blur(); // optional: remove focus
    }
  };

  return (
    <div className={`input-with-unit tooltip${className}`}>
      <input
        ref={inputRef}
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => {
          const val = Math.max(
            min,
            Math.min(max, Number(e.target.value) || min)
          );
          onChange(val);
        }}
        onFocus={(e) => e.target.select()}
        onKeyDown={handleKeyDown} // ✅ handle Enter
        placeholder={placeholder}
        className={`input-field text md text-center ${inputClassName}`}
      />
      {unit && (
        <span className={`unit-label text md${unitClassName}`}>{unit}</span>
      )}
    </div>
  );
};

// Main component
const ValueSelector = ({
  unit = "mm",
  initialValue = 1,
  min = 1,
  max = 999,
  onChange,
  value,
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentValue = value !== undefined ? value : initialValue;

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const increment = () => {
    if (currentValue < max) onChange?.(currentValue + 1);
  };
  const decrement = () => {
    if (currentValue > min) onChange?.(currentValue - 1);
  };

  return (
    <div ref={containerRef} className="value-selector pos-rel inline-block">
      {/* Trigger Button */}
      <button
        className="input-with-unit button sm fit-content dropdown"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="value-label text md">{currentValue}</span>
        <span className="unit-label text md">{unit}</span>
      </button>

      {/* Tooltip */}
      {open && (
        <div className="value-selector-container border-1 border-black elevated-sharp pos-abs flex flex-row right-0 p-1 bg-dark br-2 z-1 reveal slide-down">
          <div className="flex right-0 p-2 gap-2 bg-middark br-1 z-1">
            {/* Minus button */}
            <button
              onClick={decrement}
              className={`button icon-button close-button ${
                currentValue <= min ? "deactivated" : ""
              }`}
            >
              <span className="icon minus-icon icon-size-16"></span>
            </button>

            {/* Input */}
            <InputWithUnit
              value={currentValue}
              onChange={onChange}
              unit={unit}
              min={min}
              max={max}
              onEnter={() => setOpen(false)} // ✅ close tooltip on Enter
            />

            {/* Plus button */}
            <button
              onClick={increment}
              className={`button icon-button close-button ${
                currentValue >= max ? "deactivated" : ""
              }`}
            >
              <span className="icon plus-icon icon-size-16"></span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};


const SubactionHeader = ({ text = "2d image trackers" }) => {
  return (
    <div className="subaction-header-container gap-1 br-1 flex justify-between items-center h-25 p-1">
      <div className="text-container overflow-hidden flex items-center">
        <p className="text-nowrap text-left bg-md text-darkgray">{text}</p>
      </div>
    </div>
  );
};

/**
 * Reusable NameDropdownSelector
 * Props:
 * - options: array of strings for the buttons inside dropdown
 * - initialValue: initial selected string
 * - onChange: callback when selection changes
 * - className: additional classes for container
 */
const NameDropdownSelector = ({
  options = [],
  initialValue = "",
  onChange,
  className = "",
}) => {
  const [selected, setSelected] = useState(initialValue);
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (option) => {
    setSelected(option);
    if (onChange) onChange(option);
    setOpen(false);
  };

  return (
    <div
      ref={containerRef}
      className={`name-dropdown-selector pos-rel inline-block ${className}`}
    >
      {/* Trigger button */}
      <button
        className="gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width dropdown border-1 border-mid-black"
        onClick={() => setOpen((prev) => !prev)}
      >
        <p className="text-gray text md text-align-left text-nowrap">
          {selected || "Select..."}
        </p>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="dropdown-container border-1 border-black elevated-sharp pos-abs flex flex-col right-0 p-1 bg-dark br-2 z-1 reveal slide-down">
          <div className="flex flex-col right-0 p-1 gap-2 bg-middark br-1 z-1">
            {options.map((option, index) => (
              <button
                key={index}
                className={`gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width ${
                  selected === option ? "selected" : ""
                }`}
                onClick={() => handleSelect(option)}
              >
                <p className="text-gray text md text-align-left text-nowrap">
                  {option}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

interface TextSelectorProps {
  initialValue?: string;
  onChange?: (value: string) => void;
  value?: string;
  placeholder?: string;
}

const TextSelector: React.FC<TextSelectorProps> = ({
  initialValue = "",
  onChange,
  value,
  placeholder = "Enter text",
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const currentValue = value !== undefined ? value : initialValue;

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Focus input when dropdown opens
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [open]);

  // Close on Enter key
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setOpen(false);
      inputRef.current?.blur(); // optional: remove focus
    }
  };

  return (
    <div ref={containerRef} className="flex flex-1 text-selector pos-rel inline-block">
      {/* Trigger Button */}
      <button
        className="recording-name-field-container overflow-hidden input-with-string flex-1 button sm w-full dropdown"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="value-label text md">
          {currentValue || placeholder}
        </span>
      </button>

      {/* Tooltip / Input */}
      {open && (
        <div className="border-1 border-black elevated-sharp pos-abs flex flex-row right-0 p-1 bg-dark br-2 z-1 reveal slide-down">
          <div className=" flex right-0 p-2 gap-2 bg-middark br-1 z-1">
            <div className={`text-input`}>
              <input
                ref={inputRef}
                type="text"
                value={currentValue}
                onChange={(e) => onChange?.(e.target.value)}
                onKeyDown={handleKeyDown} // ✅ handle Enter
                placeholder={placeholder}
                className={`text-nowrap input-field text md text-center`}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


export {
  ButtonSm,
  Checkbox,
  ButtonCard,
  SegmentedControl,
  ToggleComponent,
  DropdownButton,
  ToggleButtonComponent,
  ConnectionDropdown,
  ValueSelector,
  SubactionHeader,
  NameDropdownSelector,
  TextSelector,
  // StandaloneToggleExample,
};
