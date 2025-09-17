import React, { useState } from "react";
import { ButtonSm, Checkbox } from "./uicomponents";

interface SplashModalProps {
  onClose: () => void;
}

const SplashModal: React.FC<SplashModalProps> = ({ onClose }) => {
  // Local state for checkbox - developers can hook logic here in future
  const [sendAnonymousInfo, setSendAnonymousInfo] = useState(false);

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
                <span className="color-gray-100">Free Motion Capture</span>
                <br />
                <span className="color-gray-400">for Everyone –—</span>
              </h1>

              {/* row 2 */}
              <div className="button-card-container flex gap-4">
                <div className="button items-center flex-col justify-content-space-between p-3 text-aligh-center color-gray-100 button card bg-dark flex-1 br-2 flex items-center justify-center text-gray text-xs">
                  <span className="icon m-3 live-icon icon-size-42"></span>
                  <p>Capture Live</p>
                </div>
                <div className="button items-center flex-col justify-content-space-between p-3 text-aligh-center color-gray-100 button card bg-dark flex-1 br-2 flex items-center justify-center text-gray text-xs">
                  <span className="icon m-3 import-icon icon-size-42"></span>
                  <p>Import videos</p>
                </div>
              </div>

              {/* row 3 */}
              {/* Developers: adjust the `label` text freely here */}
              <div className="flex">
                <Checkbox
                  label="Send anonymous info"
                  checked={sendAnonymousInfo} // Controlled state
                  onChange={(e) => {
                    setSendAnonymousInfo(e.target.checked); // Update state

                    // Future use: call any function with new value
                    // handleSendAnonymousInfoChange(e.target.checked);
                  }}
                />
                {"\u00A0"} {/* single between text and the hyperlink space */}
                <p className="text-gray text-sm text-align-left">
                  <a href="#" target="_blank">
                    privacy policy
                  </a>
                </p>
              </div>
            </div>

            {/* row 4 */}
            <div className="actions-bottom flex felx-1 flex-col 1gap-1">
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
