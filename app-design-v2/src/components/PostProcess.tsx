import React, { useState } from "react";
import { ButtonSm, ToggleComponent, ToggleButtonComponent } from "./uicomponents";
import clsx from "clsx";

const PostProcess = () => {
  const [processState, setProcessState] = useState("idle");

  const handleStartProcess = () => {
    console.log("Starting post-process…");
    setProcessState("running");
    setTimeout(() => setProcessState("completed"), 2000);
  };

  return (
    <>
    <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
        <div className="flex flex-row header-tool-bar br-2 gap-4">
          <div className="active-tools-header br-1-1 gap-1 p-1 flex ">
            <ButtonSm
              iconClass="process-icon"
              text={processState === "idle" ? "Start Process" : processState}
              buttonType="full-width primary justify-center"
              rightSideIcon=""
              textColor="text-white"
              onClick={handleStartProcess}
            />
          </div>
        </div>

        <div className="visualize-container overflow-y flex gap-2 flex-3 flex-start">
          <p className="text-white p-2">Post-process mode content will go here.</p>
        </div>
      </div>

      <div className="action-container flex-1 overflow-y bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
        <p className="text-white p-2">Post-process actions panel placeholder.</p>
      </div>
    </>
  );
};

export default PostProcess;
