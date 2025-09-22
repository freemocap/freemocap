
import React, {useState} from "react";

// /**
//  * ToggleComponent
//  * --------------------
//  * A reusable toggle UI component with customizable text, icons, and styles.
//  * Clicking anywhere on the parent div toggles the state.
//  *
//  * Props:
//  * ------
//  * @param {string} text - The label displayed next to the toggle.
//  * @param {React.ReactNode} [iconOn] - Icon or element for the "on" state. Default: "✔️".
//  * @param {React.ReactNode} [iconOff] - Icon or element for the "off" state. Default: "❌".
//  * @param {string} [className] - Optional class for the parent wrapper to extend/override default styles.
//  * @param {string} [iconClass] - Optional class for the dropdown icon to style it independently.
//  *
//  * Usage Example:
//  * --------------
//  * import ToggleComponent from "./components/uicomponents/ToggleComponent";
//  *
//  * function App() {
//  *   return (
//  *     <div className="flex flex-col gap-4">
//  *
//  *       {/* Default toggle */}
//  *       <ToggleComponent text="Default Toggle" />
//  *
//  *       {/* Custom icons with additional parent class */}
//  *       <ToggleComponent
//  *         text="Green Toggle"
//  *         iconOn="🟢"
//  *         iconOff="⚪"
//  *         className="green-toggle"
//  *         iconClass="custom-dropdown-icon"
//  *       />
//  *
//  *       {/* Star icons with unique styling */}
//  *       <ToggleComponent
//  *         text="Stars Toggle"
//  *         iconOn="⭐"
//  *         iconOff="☆"
//  *         className="star-toggle"
//  *         iconClass="star-dropdown-icon"
//  *       />
//  *
//  *     </div>
//  *   );
//  * }
//  *
//  * Notes for Developers:
//  * ---------------------
//  * - The `className` prop lets you customize the parent container style.
//  * - `iconClass` lets you style the dropdown icon independently.
//  * - You can pass any ReactNode to `iconOn` and `iconOff` (emoji, SVG, or JSX elements).
//  * - Clicking anywhere on the parent div toggles the state by default.
//  * - Each toggle manages its own internal state; to control externally, you could refactor to accept `isToggled` and `onToggle` props.
//  */

interface ToggleProps {
  text: string;
  className?: string;
  iconClass?: string;
  defaultToggelState?: boolean;
  isToggled?: boolean;
  onToggle?: (state: boolean) => void;
  disabled?: boolean; // new prop
}

const ToggleComponent: React.FC<ToggleProps> = ({
  text,
  className = "",
  iconClass,
  defaultToggelState = false,
  isToggled,
  onToggle,
  disabled = false,
}) => {
  const [internalToggle, setInternalToggle] = useState(defaultToggelState);

  const toggled = isToggled !== undefined ? isToggled : internalToggle;

const handleToggle = () => {
  if (disabled) return; // ignore clicks if disabled
  const newState = !toggled;
  if (isToggled === undefined) setInternalToggle(newState);
  onToggle?.(newState);
};

  return (
    <div
      className={`button toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25 ${className} ${disabled ? "disabled" : ""}`}
      onClick={handleToggle}
    >
      <div className="text-container overflow-hidden flex items-center gap-1">
        {iconClass && <span className={`icon icon-size-16 ${iconClass}`}></span>}
        <p className="text text-nowrap text-left md">{text}</p>
      </div>
      <div className={`icon toggle-container ${toggled ? "on" : "off"}`}>
        <div className="icon toggle-circle"></div>
      </div>
    </div>
  );
};
