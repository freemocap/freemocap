import React from "react";

interface SplashModalProps {
  onClose: () => void;
}

const SplashModal: React.FC<SplashModalProps> = ({ onClose }) => {
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
        <div className="flex-1 bg-middark splash-modal-inner-container br-1 gap-3 flex flex-col p-2">
        {/* close button top-right */}
       
          <button onClick={onClose} className="button icon-button close-button pos-abs top-0 right-0 m-1">
            <span className="icon close-icon icon-size-16"></span>
          </button>
       
        {/* inner content wrapper */}
        <div className="visualize-container flex flex-1 gap-2 overflow-hidden">
          {/* left column */}
          <div className="3d-container flex-1 br-2 flex flex-col items-center justify-center gap-2 splash-left-col">
            <div className="splash-image flex items-center justify-center">
              IMG
            </div>
            <div className="splash-icon flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
              </svg>
            </div>
          </div>

          {/* right column */}
          <div className="video-container flex-1 flex flex-col gap-2 p-1 splash-right-col">
            {/* row 1 */}
            <div>
              <p className="text-white font-bold text-lg">
                Free Motion Capture for Everyone –—
              </p>
            </div>

            {/* row 2 */}
            <div className="flex gap-2">
              <div className="flex-1 br-1 bg-darkgray flex items-center justify-center text-white text-xs">
                div A
              </div>
              <div className="flex-1 br-1 bg-darkgray flex items-center justify-center text-white text-xs">
                div B
              </div>
            </div>

            {/* row 3 */}
            <div>
              <p className="text-white text-sm">
                Placeholder paragraph for row 3
              </p>
            </div>

            {/* row 4 */}
            <div>
              <p className="text-white text-sm">Paragraph 1 of row 4</p>
              <p className="text-white text-sm">Paragraph 2 of row 4</p>
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
};

export default SplashModal;
