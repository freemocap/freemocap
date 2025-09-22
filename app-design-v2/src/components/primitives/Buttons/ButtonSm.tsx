import React, { useState, useEffect, useRef } from "react";
import clsx from "clsx";

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

export {
  ButtonSm
};