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
    dropdownClassName?: string; // Changed from DropdownclassName to dropdownClassName
    onClick?: () => void;
  };
  dropdownItems?: ReactNode;
  containerClassName?: string;
  dropdownClassName?: string; // Added proper prop at component level
}

export default function DropdownButton({
  buttonProps,
  dropdownItems,
  dropdownClassName, // Changed from DropdownclassName to dropdownClassName
  containerClassName,
}: DropdownButtonProps) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

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
    setOpen((prev) => !prev);
    buttonProps.onClick?.();
  };

  return (
    <div ref={buttonRef} className={clsx("flex flex-row w-full pos-rel", containerClassName)}>
      <ButtonSm {...buttonProps} onClick={handleButtonClick} />

      {open && (
        <div
          ref={popupRef}
          className={clsx("pos-abs z-111 left-0 top-30 w-full dropdown-container flex flex-row reveal slide-down elevated-sharp dropdown-container border-1 border-black bg-middark br-2 flex flex-col gap-1 p-1", dropdownClassName)}
        >
          {dropdownItems}
        </div>
      )}
    </div>
  );
}