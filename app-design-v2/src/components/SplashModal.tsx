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
        <div className="visualize-container overflow-hidden flex-1 bg-middark splash-modal-inner-container br-1 gap-3 flex flex-row p-2">
          {/* close button top-right */}

          <button
            onClick={onClose}
            className="button icon-button close-button pos-abs top-0 right-0 m-1"
          >
            <span className="icon close-icon icon-size-16"></span>
          </button>

          {/* inner content wrapper */}
          {/* <div className="visualize-container flex flex-1 gap-2 overflow-hidden"> */}
          {/* left column */}
          {/* <div className="image-container flex-1 br-2 flex flex-col items-center justify-center gap-2 splash-left-col"> */}
          <div className="splash-image-container flex flex-1">
              <div className="splash-image-logo-container m-1">
              </div>
            {/* <img.splash-logo-container
              src="./images/logo_name.svg"
              className="splash-screen-logo pos-abs left-0 top-0 m-2"
              width="88px"
              height="100%"
            ></img> */}
            {/* <img
              src="./images/splashmodal_art.webp"
              width="100%"
              height="100%"
            ></img> */}
          </div>
          {/* </div> */}

          {/* right column */}
          <div className="video-container flex-1 flex flex-col gap-2 p-1 splash-right-col">
            {/* row 1 */}
            <div>
              <h1 className="title"><span className="color-gray-100">
                Free Motion Capture for</span><br/><span className="color-gray-400">Everyone –—</span> 
              </h1>
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
          {/* </div> */}
        </div>
      </div>
    </div>
  );
};

export default SplashModal;
