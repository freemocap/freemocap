import React, {useEffect, useRef} from "react";

interface CheckboxProps {
  label: string;
  checked?: boolean;
  onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  inputClassName?: string;
  className?: string;
  disabled?: boolean;
  /** Names a box that has no visible label, for assistive technology. */
  ariaLabel?: string;
  /** Some, not all, of what the box switches is on: drawn as a bar, announced as mixed. */
  indeterminate?: boolean;
}

const Checkbox: React.FC<CheckboxProps> = ({
  label,
  checked = false,
  onChange,
  inputClassName = "",
  className = "",
  disabled = false,
  ariaLabel,
  indeterminate = false,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  /*
   * "Partly on" is a DOM property with no HTML attribute, and the browser
   * clears it whenever the box is clicked, so it is set after every render.
   */
  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = indeterminate;
  });

  return (
    <label
      className={`
        checkbox
        text-nowrap
        button
        p-2
        select-none
        cursor-pointer
        ${className}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
      `}
    >
      <input
        ref={inputRef}
        type="checkbox"
        aria-label={ariaLabel}
        aria-checked={indeterminate ? "mixed" : undefined}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className={`
          button
          flex-shrink-0
          ${inputClassName}
        `.trim()}
      />

      <p className="text-gray text md text-align-left">
        {label}
      </p>
    </label>
  );
};

export default Checkbox;
