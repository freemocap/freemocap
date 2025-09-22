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


export const ButtonCard = ({ text, iconClass, onClick, className = "" }) => {
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
