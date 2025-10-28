import React from "react";

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
          const syntheticEvent = {
            ...e,
            target: {
              ...e.target,
              checked: !checked,
            },
          } as React.ChangeEvent<HTMLInputElement>;
          onChange(syntheticEvent);
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

export default Checkbox;
