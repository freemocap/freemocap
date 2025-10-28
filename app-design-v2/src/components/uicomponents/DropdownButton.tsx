import React, { useState, useEffect, useRef, ReactNode } from "react";
import clsx from "clsx";
import ButtonSm from "./ButtonSm";

/* Dropdown button */

interface DropdownButtonProps {
  buttonProps: {
    text: string;
    iconClass?: string;
    rightSideIcon?: string;
    textColor?: string;
    buttonType?: string;
    onClick?: () => void; // optional, in addition to dropdown toggle
  };
  dropdownItems?: ReactNode; // any JSX to render inside dropdown
  containerClassName?: string; // NEW: optional classes for the container div
}

export default function DropdownButton({
  buttonProps,
  dropdownItems,
  containerClassName, // NEW: allow external classes
}: DropdownButtonProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleButtonClick = () => {
    // Toggle dropdown
    setOpen((prev) => !prev);
    // Run any additional onClick passed to the main button
    buttonProps.onClick?.();
  };

  return (
    <div
      ref={containerRef}
      // Default classes + any custom ones provided
      className={clsx("flex flex-col z-2", containerClassName)}
    >
      <ButtonSm
        {...buttonProps}
        onClick={handleButtonClick} // wraps dropdown toggle + optional extra onClick
      />

      {open && (
        <div
          className="reveal slide-down dropdown-container border-1 border-black bg-middark br-2 pos-abs flex flex-col gap-1 p-1"
          style={{ top: "33px" }}
        >
          {dropdownItems}
        </div>
      )}
    </div>
  );
}
