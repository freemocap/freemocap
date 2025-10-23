import React, { useState, useEffect } from "react";

interface IconSegmentedControlOption {
  value: string;
  iconClass: string; // e.g., "stream-icon", "record-icon", etc.
}

interface IconSegmentedControlProps {
  options: IconSegmentedControlOption[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
}

const IconSegmentedControl: React.FC<IconSegmentedControlProps> = ({
  options,
  defaultValue,
  value: controlledValue,
  onChange,
}) => {
  const isControlled = controlledValue !== undefined;
  const [activeValue, setActiveValue] = useState(
    isControlled ? controlledValue : defaultValue || options[0]?.value
  );

  // Keep in sync if controlled
  useEffect(() => {
    if (isControlled && controlledValue !== activeValue) {
      setActiveValue(controlledValue);
    }
  }, [controlledValue, isControlled, activeValue]);

  const handleClick = (value: string) => {
    if (!isControlled) setActiveValue(value);
    onChange?.(value);
  };

  const activeOption = options.find((opt) => opt.value === activeValue);

  return (
    // <div className="icon-only segmented-control-container br-1-1 gap-1 p-1 bg-middark flex">
      <button
        className="button icon-button pos-rel segmented-control-icon"
        onClick={() => {
          // find current index and toggle to next icon
          const currentIndex = options.findIndex(
            (opt) => opt.value === activeValue
          );
          const nextIndex = (currentIndex + 1) % options.length;
          handleClick(options[nextIndex].value);
        }}
      >
        <span
          className={`icon ${
            activeOption?.iconClass || options[0]?.iconClass
          } icon-size-16`}
        ></span>
      </button>
    // </div>
  );
};

export default IconSegmentedControl;