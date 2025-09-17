import React, { useState } from "react";
import { ButtonSm, Checkbox, ButtonCard } from "./uicomponents";

interface SplashModalProps {
  onClose: () => void;
}

const SplashModal: React.FC<SplashModalProps> = ({ onClose }) => {
  // Local state for checkbox - developers can hook logic here in future
  const [sendAnonymousInfo, setSendAnonymousInfo] = useState(false);

  /* Closing popup and Escape key pressed */
    React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);


  return (
    <div
      className="splash-overlay inset-0"
      onClick={onClose} // clicking overlay closes modal
    >
      {/* modal container */}
      <div
        className="splash-modal main-container br-2 flex flex-col p-1 bg-dark border-1 border-black"
        onClick={(e) => e.stopPropagation()} // prevent overlay click from closing when clicking inside
      >
        <div className="visualize-container overflow-hidden flex-1 bg-middark splash-modal-inner-container br-1 gap-3 flex flex-row p-2">
          {/* close button top-right */}
          <button
            onClick={onClose}
            className="button icon-button close-button pos-abs top-0 right-0 m-1"
          >
            <span className="icon close-icon icon-size-16"></span>
          </button>

          {/* left column */}
          <div className="splash-image-container flex flex-1">
            <div className="splash-image-logo-container m-2"></div>
          </div>

          {/* right column */}
          <div className="splash-right-col flex-1 flex flex-col gap-2 p-1 justify-content-space-between">
            {/* row 1 */}
            <div className="actions-top flex felx-1 flex-col p-1 gap-3">
              <h1 className="title">
                <span className="text-white">Free Motion Capture</span>
                <br />
                <span className="text-gray">for Everyone –—</span>
              </h1>

              {/* row 2 */}
              
              <div className="button-card-container flex gap-4">
              {/* /**
              * Example of a separate handler function
              * --------------------------------------
              * - Use this approach if:
              *   1. The logic is complex (API calls, state updates, navigation).
              *   2. You need to reuse the same click action in multiple places.
              *   3. You want to keep the JSX cleaner and easier to read.
              *   4. You plan to test this function in isolation.
              */ }
              {/* const handleLiveClick = () => {
                console.log("Capture Live button clicked!"); */}
                {/* // 👉 Here you can:
                // - Trigger camera capture
                // - Call an API endpoint
                // - Dispatch a Redux action
                // - Navigate to another route (React Router)
              }; */}
              
              {/* /*
                Example 1: Using inline onClick function
                ----------------------------------------
                - Good for short, one-off logic.
                - Keeps everything self-contained in one place.
                - ⚠️ Avoid for long or repeated logic (becomes messy). */}
              
                          <ButtonCard
                  text="Capture Live"
                  iconClass="live-icon icon-size-42"
                  onClick={() => {
                    console.log("Inline Capture Live clicked");
                    // 👉 Quick actions like logging, simple UI feedback, or toggles.
                  }}
                />
                                   <ButtonCard
                  text="Import videos"
                  iconClass="import-icon icon-size-42"
                  onClick={() => {
                    console.log("Inline Capture Live clicked");
                    // 👉 Quick actions like logging, simple UI feedback, or toggles.
                  }}
                />
              </div>

              {/* row 3 */}
              {/* Developers: adjust the `label` text freely here */}
              <div className="flex">
                <Checkbox
                  label="Send anonymous info"
                  checked={sendAnonymousInfo} // Controlled state
                  onChange={(e) => {
                    setSendAnonymousInfo(e.target.checked); // Update state
                    console.log("send anynymous info clicked");
                    // Future use: call any function with new value
                    // handleSendAnonymousInfoChange(e.target.checked);
                  }}
                />
                ,{"\u00A0"} {/* single between text and the hyperlink space */}
                <a className="text sm" href="#" target="_blank">
                    privacy policy
                  </a>
                
              </div>
            </div>

            {/* row 4 */}
            <div className="actions-bottom flex felx-1 flex-col gap-1">
              {/* Replaced raw buttons with reusable ButtonSm component */}
              <ButtonSm
                iconClass="learn-icon"
                text="Learn how to use FreeMocap"
                externalLink={true}
                onClick={() => {
                  // Developers: Replace this with navigation or tutorial logic
                  console.log("Learn how to use FreeMocap clicked");
                }}
              />

              <ButtonSm
                iconClass="discord-icon"
                text="Join community"
                externalLink={true}
                onClick={() => {
                  // Developers: Replace this with navigation to community page
                  console.log("Join community clicked");
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SplashModal;
