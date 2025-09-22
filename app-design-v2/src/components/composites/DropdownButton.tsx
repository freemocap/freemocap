import {type ReactNode, useEffect, useRef, useState} from "react";
import clsx from "clsx";
import {ButtonSm} from "@/components/primitives/Buttons/ButtonSm.tsx";

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

--------------------------------------------------------------------------
 */
