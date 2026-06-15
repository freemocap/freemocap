import React, { useState, useEffect, useRef } from "react";

interface NameDropdownSelectorProps {
  options?: string[];
  initialValue?: string;
  onChange?: (value: string) => void;
  className?: string;
  DropdownclassName?: string;
}

const NameDropdownSelector: React.FC<NameDropdownSelectorProps> = ({
  options = [],
  initialValue = "",
  onChange,
  className = "",
  DropdownclassName = "",
}) => {
  const [selected, setSelected] = useState(initialValue);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (option: string) => {
    setSelected(option);
    onChange?.(option);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className={`name-dropdown-selector min-w-0 w-inherit pos-rel inline-block ${className}`}>
      <button
        className="flex flex-1 min-w-full flex-1 gap-1 br-1 button sm flex-inline text-left items-center dropdown border-1 border-mid-black"
        onClick={() => setOpen((prev) => !prev)}
      >
        <p className="text-gray text md text-align-left text-nowrap">
          {selected || "Select..."}
        </p>
      </button>

      {open && (
        <div className={`dropdown-container top-30 border-1 min-w-full border-black elevated-sharp pos-abs flex flex-col right-0 p-1 bg-dark br-2 z-1 reveal slide-down ${DropdownclassName}`}>
          <div className="w-full flex flex-col right-0 p-1 gap-2 bg-middark br-1 z-1">
            {options.map((option, index) => (
              <button
                key={index}
                className={`w-full gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width ${selected === option ? "selected" : ""}`}
                onClick={() => handleSelect(option)}
              >
                <p className="text-gray text md text-align-left text-nowrap">{option}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NameDropdownSelector;