import clsx from "clsx";


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
