import React, { useState, useEffect, useRef } from "react";

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
    <div
      ref={containerRef}
      className="flex flex-1 text-selector pos-rel inline-block"
    >
      {/* Trigger Button */}
      <button
        className="recording-name-field-container overflow-hidden input-with-string flex-1 button sm w-full dropdown"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="text-nowrap value-label text md">
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

export default TextSelector;
