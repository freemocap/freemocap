import React, { useState, useEffect } from "react";
import { ButtonSm, ToggleComponent, ToggleButtonComponent, SegmentedControl, ValueSelector } from "../uicomponents";
import clsx from "clsx";

const CaptureLive = () => {
  // Stream state
  const [streamState, setStreamState] = useState("disconnected");

  // Calibration & toggles
  const [skipCalibration, setSkipCalibration] = useState(true);


  const [selectedValue, setSelectedValue] = useState(10);


  // Functions (duplicated & isolated for ModeCaptureLive)
  const handleStreamConnect = () => {
    console.log("Checking before streaming…");
    setStreamState("connecting");
    setTimeout(() => setStreamState("connected"), 2000);
  };
  const handleStreamDisconnect = () => {
    console.log("Stopped streaming!");
    setStreamState("disconnected");
  };

  return (
    <>
      {/* mode-container */}
      <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
        <div className="flex flex-row header-tool-bar br-2 gap-4">
          {/* You can still keep SegmentedControl here if needed */}
          <div className="reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex ">
            <ToggleButtonComponent
              state={streamState}
              connectConfig={{
                text: "Stream Camera",
                iconClass: "stream-icon",
                rightSideIcon: "",
                extraClasses: "",
              }}
              connectingConfig={{
                text: "Checking...",
                iconClass: "loader-icon",
                rightSideIcon: "",
                extraClasses: "loading disabled",
              }}
              connectedConfig={{
                text: "Streaming...",
                iconClass: "streaming-icon",
                rightSideIcon: "",
                extraClasses: "activated",
              }}
              textColor="text-white"
              onConnect={handleStreamConnect}
              onDisconnect={handleStreamDisconnect}
            />
          </div>
        </div>

        <div className="reveal fadeIn visualize-container flex gap-2 flex-3 flex-start">
          <div className="video-container flex flex-row flex-wrap gap-2 flex-1 flex-start">
            {[...Array(6)].map((_, idx) => (
              <div key={idx} className="video-tile camera-source size-1 bg-middark br-2 empty" />
            ))}
          </div>
        </div>
      </div>

      <div className="reveal fadeIn action-container flex-1 overflow-y bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
        <div className="subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
          <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
                   {/* text input container numeric value */}
            <div class="text-input-container gap-1 br-1 flex justify-content-space-between items-center h-25  ">
              <div class="text-container overflow-hidden flex items-center">
                {/* explainer icon */}
                <button onClick="" className="button icon-button close-button">
                  <span className="icon explainer-icon icon-size-16"></span>
                </button>

                <p class="text text-nowrap text-left md">Charuco size</p>
              </div>
              <ValueSelector
                unit="mm"
                initialValue={selectedValue}
                onChange={(val) => setSelectedValue(val)}
              />
              
            </div>
               <ButtonSm
                          iconClass="calibrate-icon"
                          text="Calibrate"
                          buttonType="full-width secondary justify-center"
                          rightSideIcon=""
                          textColor="text-white"
                          onClick={() => console.log("Calibrate clicked")}
                        />
            <ToggleComponent
              text="Skip calibration"
              className=""
              iconClass=""
              defaultToggelState={true}
              isToggled={skipCalibration}
              onToggle={setSkipCalibration}
            />
          </div>

          <div
            className={clsx(
              "flex flex-col record-container br-1 p-1 gap-1 bg-middark reveal",
              { disabled: !skipCalibration }
            )}
          >
            <ToggleComponent text="Auto process save" className="" iconClass="" />
            <ToggleComponent text="Generate jupyter notebook" className="" iconClass="" />
            <ToggleComponent text="Auto open Blender" className="" iconClass="" defaultToggelState={true} />
            <ButtonSm
              iconClass="record-icon"
              text="Record"
              buttonType="full-width primary justify-center"
              rightSideIcon=""
              textColor="text-white"
              onClick={() => console.log("Record clicked")}
            />
            <div className="p-1 g-1">
              <p className="text bg-md text-left">
                Camera views may lag at higher settings. Try lowering the resolution/reducing the number of cameras. fix is coming soon.
              </p>
            </div>
          </div>
        </div>

      </div>
    </>
  );
};

export default CaptureLive;
