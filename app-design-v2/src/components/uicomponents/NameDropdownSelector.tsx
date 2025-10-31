import React, { useState, useEffect, useRef } from "react";

/**
 * Reusable NameDropdownSelector
 * Props:
 * - options: array of strings for the buttons inside dropdown
 * - initialValue: initial selected string
 * - onChange: callback when selection changes
 * - className: additional classes for container
 */
interface NameDropdownSelectorProps {
  options?: string[];
  initialValue?: string;
  onChange?: (value: string) => void;
  className?: string;
}

const NameDropdownSelector: React.FC<NameDropdownSelectorProps> = ({
  options = [],
  initialValue = "",
  onChange,
  className = "",
}) => {
  const [selected, setSelected] = useState(initialValue);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
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

  const handleSelect = (option: string) => {
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

export default NameDropdownSelector;
