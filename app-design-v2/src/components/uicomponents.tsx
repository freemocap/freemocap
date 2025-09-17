import React from "react";


// PROPS for ButtonSm:
// - iconClass (string): class name for the icon (e.g., "live-icon").
// - text (string): the button label text.
// - onClick (function): the action to run when button is clicked.
//   If none is provided, it defaults to a no-op function.
const ButtonSm = ({ iconClass, text, onClick = () => {}, externalLink = false }) => {
  return (
    <button
    className={`gap-1 br-1 button sm flex-inline text-left items-center ${externalLink ? "externallink" : ""}`}
    onClick={onClick} // <-- Attach your custom function here
    >
      {/* ICON SECTION */}
      {/* "icon-size-16" ensures a consistent icon size. */}
      {/* iconClass is dynamic, so pass in something like "live-icon" */}
      <span className={`icon ${iconClass} icon-size-16`}></span>

      {/* TEXT SECTION */}
      {/* text prop sets the button label. */}
      <p className="text-gray text md text-align-left">{text}</p>
    </button>
  );
};


/**
 * Reusable Checkbox Component
 * ----------------------------
 * - Combines a native <input type="checkbox"> with a text label (<p> tag).
 * - Use the `label` prop to change the string next to the checkbox.
 * - `checked` + `onChange` make this component controllable from parent state.
 * - The entire container is clickable to toggle the checkbox.
*/

interface CheckboxProps {
  label: string; // text shown next to the checkbox (developers can change this freely)
  checked?: boolean; // optional controlled state
  onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void; // handler for state changes
}

const Checkbox: React.FC<CheckboxProps> = ({ label, checked, onChange }) => {
  return (
    <div
    className="button checkbox gap-1 flex flex-row items-center"
    onClick={(e) => {
        // Allow clicking anywhere on the container to toggle checkbox
        if (onChange) {
          onChange({
            ...e,
            target: { ...(e.target as HTMLInputElement), checked: !checked },
          } as React.ChangeEvent<HTMLInputElement>);
        }
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="button"
      />
      <p className="text-gray text sm text-align-left">{label}</p>
    </div>
  );
};


/**
* ButtonCard Component
* --------------------
* A reusable UI component that displays a card-like button with:
* - An icon (customizable via CSS class)
* - A text label (string passed as a prop)
* - A click handler (function passed as a prop)
*
* Props:
* ------
* @param {string} text - The text displayed under the icon.
* @param {string} iconClass - The class(es) applied to the <span> element for styling the icon.
* Example: "live-icon icon-size-42".
* @param {function} onClick - The function triggered when the button is clicked.
* @param {string} [className] - (Optional) Additional classes to extend/override the default wrapper styles.
*
* Usage Example:
* --------------
* import ButtonCard from "./ButtonCard";
*
* function App() {
* const handleLiveClick = () => {
* console.log("Capture Live button clicked!");
* };
*
* return (
* <div className="flex gap-4">
* <ButtonCard
* text="Capture Live"
* iconClass="live-icon icon-size-42"
* onClick={handleLiveClick}
* />
*
* <ButtonCard
* text="Upload File"
* iconClass="upload-icon icon-size-42"
* onClick={() => alert("Upload File clicked")}
* className="bg-blue-600"
* />
* </div>
* );
* }
*
* Notes for Developers:
* ---------------------
* - The `iconClass` lets you swap out icons dynamically by just changing the class string.
* - If you need SVG or inline icons, you can refactor to accept an `icon` ReactNode prop instead.
* - The default styling is based on the original HTML snippet (dark background, flex, centered).
* Override or extend using the optional `className` prop.
*/


const ButtonCard = ({ text, iconClass, onClick, className = "" }) => {
return (
<div
className={`button items-center flex-col justify-content-space-between p-3 text-aligh-center button card bg-dark flex-1 br-2 flex items-center justify-center text-white text-xs ${className}`}
onClick={onClick}
>
{/* Icon section - styled via passed classes */}
<span className={`icon m-3 ${iconClass}`}></span>


{/* Text section */}
<p className="text-center text bg">{text}</p>
</div>
);
};



export { ButtonSm, Checkbox, ButtonCard };
