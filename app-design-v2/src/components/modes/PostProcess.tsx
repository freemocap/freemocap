import React, { useState } from "react";
import { ButtonSm, ToggleComponent, ToggleButtonComponent } from "../uicomponents";
import clsx from "clsx";

const PostProcess = () => {

  const HandleImportVideos = () => {
    console.log("Starting post-process…");
    setTimeout(() => console.log("Improt videos button clicked"));
  };

  return (
    <>
    <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
        <div className="flex flex-row header-tool-bar br-2 gap-4">
          <div className="active-tools-header br-1-1 gap-1 p-1 flex ">
            <ButtonSm
              iconClass="import-icon"
              text="Import videos"
              buttonType=""
              rightSideIcon=""
              textColor="text-white"
              onClick={HandleImportVideos}
            />
          </div>
        </div>

        <div className="visualize-container overflow-hidden flex-row  flex gap-2 flex-3 flex-start">
                <div className="3D-container br-2 flex flex-row flex-wrap gap-2 flex-2 flex-start bg-middark h-full">


                </div>

                <div className="align-content-start align-start video-container overflow-y flex flex-row flex-wrap gap-2 flex-3 flex-start h-full">
                        {[...Array(6)].map((_, idx) => (
                          <div key={idx} className="video-tile size-1 bg-middark br-2 empty" />
                        ))}
                </div>

        </div>
      </div>

      <div className="action-container flex-1 overflow-y bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
        <p className="text-white p-2">Post-process actions panel placeholder.</p>
      </div>
    </>
  );
};

export default PostProcess;
