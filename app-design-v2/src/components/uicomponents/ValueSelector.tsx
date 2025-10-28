import React, { useState, useEffect, useRef } from "react";

// Reusable InputWithUnit
interface InputWithUnitProps {
  value: number;
  onChange: (value: number) => void;
  unit?: string;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  unitClassName?: string;
  min?: number;
  max?: number;
  onEnter?: () => void;
}

const InputWithUnit: React.FC<InputWithUnitProps> = ({
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
interface ValueSelectorProps {
  unit?: string;
  initialValue?: number;
  min?: number;
  max?: number;
  onChange?: (value: number) => void;
  value?: number;
}

const ValueSelector: React.FC<ValueSelectorProps> = ({
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
              onChange={onChange || (() => {})}
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

export default ValueSelector;
