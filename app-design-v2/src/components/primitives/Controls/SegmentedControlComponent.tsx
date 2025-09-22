import React, {useEffect, useState} from "react";



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
