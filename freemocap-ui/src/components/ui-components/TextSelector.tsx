import React, { useState, useEffect, useRef } from "react";

interface TextSelectorProps {
  initialValue?: string;
  onChange?: (value: string) => void;
  value?: string;
  placeholder?: string;
  popupClassName?: string;
}

const TextSelector: React.FC<TextSelectorProps> = ({
  initialValue = "",
  onChange,
  value,
  placeholder = "Enter text",
  popupClassName = "",
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const currentValue = value !== undefined ? value : initialValue;

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

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-1 text-selector pos-rel inline-block"
    >
      <button
        className="recording-name-field-container overflow-hidden input-with-string flex-1 button sm w-full dropdown"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="text-nowrap value-label text md">
          {currentValue || placeholder}
        </span>
      </button>

      {open && (
        <div
          className={`string-selector pos-abs border-1 w-full border-black elevated-sharp flex flex-row  p-1 bg-dark br-2 z-1 reveal slide-down ${popupClassName}`}
        >
          <div className="min-w-full flex p-2 gap-2 bg-middark br-1">
            <div className="text-input">
              <input
                ref={inputRef}
                type="text"
                value={currentValue}
                onChange={(e) => onChange?.(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                className={`text-nowrap input-field text md text-center ${popupClassName}`}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TextSelector;
