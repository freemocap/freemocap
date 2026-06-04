import React, { useState, useEffect, useRef, ReactNode } from "react";
import clsx from "clsx";
import ButtonSm from "./ButtonSm";

interface DropdownButtonProps {
  buttonProps: {
    text: string;
    iconClass?: string;
    rightSideIcon?: string;
    textColor?: string;
    buttonType?: string;
    className?: string;
    onClick?: () => void;
  };
  dropdownItems?: ReactNode;
  containerClassName?: string;
} 

export default function DropdownButton({
  buttonProps,
  dropdownItems,
  containerClassName,
}: DropdownButtonProps) {
  const [open, setOpen] = useState(false);
  const [popupStyle, setPopupStyle] = useState<React.CSSProperties>({});
  const buttonRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (
        popupRef.current && !popupRef.current.contains(event.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleButtonClick = () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();

    }
    setOpen((prev) => !prev);
    buttonProps.onClick?.();
  };

  return (
    <div ref={buttonRef} className={clsx("pos-rel", containerClassName)}>
      <ButtonSm {...buttonProps} onClick={handleButtonClick} />

      {open && (
        <div
          ref={popupRef}
          className="connection-status-dropdown flex flex-row reveal slide-down elevated-sharp dropdown-container border-1 border-black bg-middark br-2 flex flex-col gap-1 p-1"
          
        >
          {dropdownItems}
        </div>
      )}
    </div>
  );
}
