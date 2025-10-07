import React from "react";

const ExcludedCameraTooltip = () => {
  return (
    <div className="reveal fadeIn z-2 pos-abs gap-1 rounded br-1 tooltip warning excluded-camera-tooltip inline-flex items-center p-2 bg-dark text-left fit-content">
      {/* <span className="icon icon-size-16 warning-icon"></span> */}
      <p className="text-nowrap"><span className="text-warning">Excluded</span>, Camera not used in recording</p>
    </div>
  );
};

export default ExcludedCameraTooltip;
