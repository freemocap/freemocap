import React, { useState, useEffect, useLayoutEffect, useRef } from "react";
import ReactDOM from "react-dom";

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
  const [openUpward, setOpenUpward] = useState(false);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({ position: "fixed", top: 0, right: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current && !containerRef.current.contains(e.target as Node) &&
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useLayoutEffect(() => {
    if (!open || !containerRef.current) return;

    const gap = 4;
    const buttonRect = containerRef.current.getBoundingClientRect();
    const dropdownHeight = dropdownRef.current?.getBoundingClientRect().height ?? 0;
    const upward = buttonRect.bottom + dropdownHeight + gap > window.innerHeight;

    setOpenUpward(upward);
    setMenuStyle({
      position: "fixed",
      right: window.innerWidth - buttonRect.right,
      ...(upward
        ? { bottom: window.innerHeight - buttonRect.top + gap }
        : { top: buttonRect.bottom + gap }),
    });
  }, [open, options.length]);

  const handleSelect = (option: string) => {
    setSelected(option);
    onChange?.(option);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className={`name-dropdown-selector pos-rel inline-block ${className}`}>
      <button
        className="gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width dropdown border-1 border-mid-black"
        onClick={() => setOpen((prev) => !prev)}
      >
        <p className="text-gray text md text-align-left text-nowrap">
          {selected || "Select..."}
        </p>
      </button>

      {open && ReactDOM.createPortal(
        <div
          ref={dropdownRef}
          style={{ ...menuStyle, zIndex: 1000 }}
          className={`dropdown-container border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal ${openUpward ? "slide-up" : "slide-down"} ${DropdownclassName}`}
        >
          <div className="flex flex-col right-0 p-1 gap-2 bg-middark br-1 z-1">
            {options.map((option, index) => (
              <button
                key={index}
                className={`gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width ${selected === option ? "selected" : ""}`}
                onClick={() => handleSelect(option)}
              >
                <p className="text-gray text md text-align-left text-nowrap">{option}</p>
              </button>
            ))}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

export default NameDropdownSelector;
