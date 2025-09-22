import React, { useState, useEffect, useRef, type ReactNode } from "react";
import clsx from "clsx";

<<<<<<< HEAD
// Example usage:
// --------------
// const [mode, setMode] = useState("live");
// <SegmentedControl
//   options={[
//     { label: "Live Capture", value: "live", iconClass: "live-icon" },
//     { label: "Post-process", value: "post", iconClass: "post-icon" },
//   ]}
//   defaultValue="live"
//   onChange={setMode}
// />

// PROPS for ButtonSm:
// - iconClass (string): class name for the icon (e.g., "live-icon").
// - text (string): the button label text.
// - onClick (function): the action to run when button is clicked.
//   If none is provided, it defaults to a no-op function.

const ButtonSm = ({
  iconClass = "", // left-side icon
  buttonType = "", // valid types are : use classes like this  // for primaruy use: primary full-width justify-center // for secondary use " secondary full-width justify-center ""
  text,
  onClick = () => {},
  rightSideIcon = "", // "externallink" | "dropdown" | ""
  textColor = "text-gray", // "text-gray" | "text-white"
}) => {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "gap-1 br-1 button sm flex-inline text-left items-center", // base styles
        buttonType, // multiple classes supported here
        rightSideIcon // this is being treated as classes, same as before
      )}
    >
      {/* LEFT ICON */}
      {iconClass && <span className={clsx("icon icon-size-16", iconClass)} />}

      {/* TEXT */}
      <p className={clsx(textColor, "text md text-align-left")}>{text}</p>
    </button>
  );
};




/* Dropdown button */

/* DropdownButtonProps */
interface DropdownButtonProps {
  buttonProps: {
    text: string;
    iconClass?: string;
    rightSideIcon?: string;
    textColor?: string;
    buttonType?: string;
    onClick?: () => void;
  };
  dropdownItems?: ReactNode; // <--- ReactNode imported
  containerClassName?: string;
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

/* --------------------------------------------------------------------------
USAGE EXAMPLES

1. Basic usage (same as before, default container styling):

<DropdownButton
  buttonProps={{ text: "Menu" }}
  dropdownItems={<div>Item 1</div>}
/>

2. Add custom styles to the container:

<DropdownButton
  buttonProps={{ text: "Menu" }}
  dropdownItems={<div>Item 1</div>}
  containerClassName="items-end bg-gray-800"
/>

➡ This will merge the default classes (flex flex-col z-2 align-end) with your
   provided classes (items-end bg-gray-800).

3. Advanced example with extra button props:

<DropdownButton
  buttonProps={{
    text: "Settings",
    iconClass: "icon-gear",
    textColor: "text-white",
    buttonType: "primary",
    onClick: () => console.log("Main button clicked"),
  }}
  dropdownItems={
    <>
      <div>Profile</div>
      <div>Logout</div>
    </>
  }
  containerClassName="w-48 border rounded shadow-lg"
/>

-------------------------------------------------------------------------- */


export {
  ButtonSm,
  DropdownButton
};
=======

export const ButtonSm = ({
                      iconClass = "", // left-side icon
                      buttonType = "", // valid types are : use classes like this  // for primaruy use: primary full-width justify-center // for secondary use " secondary full-width justify-center ""
                      text = "Button",
                      onClick = () => {},
                      rightSideIcon = "", // "externallink" | "dropdown" | ""
                      textColor = "text-gray", // "text-gray" | "text-white"
                  }) => {
    return (
        <button
            onClick={onClick}
            className={clsx(
                "gap-1 br-1 button sm flex-inline text-left items-center", // base styles
                buttonType, // multiple classes supported here
                rightSideIcon // this is being treated as classes, same as before
            )}
        >
            {/* LEFT ICON */}
            {iconClass && <span className={clsx("icon icon-size-16", iconClass)} />}

            {/* TEXT */}
            <p className={clsx(textColor, "text md text-align-left")}>{text}</p>
        </button>
    );
};
>>>>>>> parent of dc3ba20b (bringing back the original codebase)
