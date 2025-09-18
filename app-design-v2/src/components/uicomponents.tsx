import React, { useState, useEffect } from "react";

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
    <div className={`segmented-control-container br-1-1 gap-1 p-1 bg-middark flex ${className}`}>
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
  text,
  onClick = () => {},
  rightSideIcon = "", // "externallink" | "dropdown" | ""
  textColor = "text-gray", // "text-gray" | "text-white"
}) => {
  return (
    <button
      className={`gap-1 br-1 button sm flex-inline text-left items-center ${rightSideIcon}`}
      onClick={onClick}
    >
      {/* LEFT ICON */}
      {iconClass && <span className={`icon ${iconClass} icon-size-16`} />}

      {/* TEXT */}
      <p className={`${textColor} text md text-align-left`}>{text}</p>
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
      className="button checkbox gap-1 flex flex-row items-center"
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



export { ButtonSm, Checkbox, ButtonCard, SegmentedControl };
