import React from "react";

interface CheckboxProps {
  label: string; // text shown next to the checkbox (developers can change this freely)
  checked?: boolean; // optional controlled state
  onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void; // handler for state changes
}

// PROPS for ButtonSm:
// - iconClass (string): class name for the icon (e.g., "live-icon").
// - text (string): the button label text.
// - onClick (function): the action to run when button is clicked.
//   If none is provided, it defaults to a no-op function.
const ButtonSm = ({ iconClass, text, onClick = () => {}, externalLink = false }) => {
  return (
    <button
      className={`gap-1 br-1 button sm flex-inline text-left items-center ${externalLink ? "externallink" : ""}`}
      onClick={onClick} // <-- Attach your custom function here
    >
      {/* ICON SECTION */}
      {/* "icon-size-16" ensures a consistent icon size. */}
      {/* iconClass is dynamic, so pass in something like "live-icon" */}
      <span className={`icon ${iconClass} icon-size-16`}></span>

      {/* TEXT SECTION */}
      {/* text prop sets the button label. */}
      <p className="text-gray text-sm text-align-left">{text}</p>
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
      <p className="button text-gray text-sm text-align-left">{label}</p>
    </div>
  );
};

// ✅ Correct export pattern
// - Use named exports for multiple components in one file.
// - Developers can import like:
//   import { ButtonSm, Checkbox } from "./uicomponents";
export { ButtonSm, Checkbox };
