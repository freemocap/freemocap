import React, { useState, useEffect } from "react";
import {
  ButtonSm,
  ToggleComponent,
  ToggleButtonComponent,
  SegmentedControl,
  ValueSelector,
  SubactionHeader,
} from "../uicomponents";
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

  const [Countdown, setCountdown] = useState(false);
  const [CounterValue, setCounterValue] = useState(3);

  const [timeStampPrefix, settimeStampPrefix] = useState(false);

  const [AutoIncrement, setAutoIncrement] = useState(false);

  const [AutoIncrementValue, setAutoIncrementValue] = useState(3);

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

        <div className="reveal overflow-y fadeIn visualize-container flex gap-2 flex-3 flex-start">
          <div className="video-container flex flex-row flex-wrap gap-2 flex-1 flex-start">
            {[...Array(6)].map((_, idx) => (
              <div
                key={idx}
                className="video-tile camera-source size-1 bg-middark br-2 empty"
              />
            ))}
          </div>
        </div>
      </div>

      <div className="reveal fadeIn action-container flex-1 bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
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
            <ToggleComponent
              text="Auto process save"
              className=""
              iconClass=""
            />
            <ToggleComponent
              text="Generate jupyter notebook"
              className=""
              iconClass=""
            />
            <ToggleComponent
              text="Auto open Blender"
              className=""
              iconClass=""
              defaultToggelState={true}
            />

            {/* button to trigger the folder directory settings */}

            <div className="record-group flex flex-col gap-1 border-1 border-mid-black br-2 p-1 pb-2">
              <ButtonSm
                iconClass="record-icon"
                text="Record"
                buttonType="full-width primary justify-center"
                rightSideIcon=""
                textColor="text-white"
                onClick={() => console.log("Record clicked")}
              />

              <div className="trigger-file-directory-settings overflow-hidden button modal-trigger-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                {/* <p className="gap-1 flex flex-row"> */}

                <span class="folder-directory overflow-hidden text-nowrap text md">
                  D:\Users\pooyasondeperson
                </span>

                <span class="subfolder-directory overflow-hidden text-nowrap text md">
                  Subfolder_name
                </span>

                {/* </p> */}

                <button class="button icon-button pos-rel top-0 right-0">
                  <span class="icon settings-icon icon-size-16"></span>
                </button>
              </div>

              <ToggleComponent
                text="Countdown"
                className=""
                iconClass=""
                isToggled={Countdown}
                onToggle={setCountdown}
              />
              <div
                className={clsx(
                  "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                  { disabled: !Countdown }
                )}
              >
                <div className="gap-1 text-container overflow-hidden flex items-center">
                  <span className="icon icon-size-16 subcat-icon"></span>
                  <p className="text text-nowrap text-left md">Start after</p>
                </div>
                <ValueSelector
                  unit="s"
                  min={1}
                  max={120}
                  initialValue={CounterValue}
                  onChange={setCounterValue}
                />
              </div>
            </div>

            <div className="file-directory-settings-modal modal border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1">
              <div className="flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
                <SubactionHeader text="Recording directory" />
                <div class="flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block gap-1">
                  <button class="overflow-hidden flex-1 flex input-with-unit button sm select-folder gap-1">
                      <span class="text-nowrap value-label text md">
                        C:\Users\pooyasonsdsdsdsdsd
                      </span>
                  </button>
                  {/* addsubfolder button top-right */}
                  <button
                    onClick={""}
                    className="button icon-button close-button pos-rel top-0 right-0"
                  >
                    <span className="icon addsubfolder-icon icon-size-16"></span>
                  </button>
                </div>
                <div class="items-center gap-1 flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block">
                  <span className="icon subcat-icon icon-size-16"></span>
                  <button class="overflow-hidden flex-1 flex input-with-unit button sm dropdown">
                    <span class="text-nowrap value-label text md">
                      Subfolder_name
                    </span>
                  </button>
                  {/* minus or remove buttoons top-right */}
                  <button
                    onClick={""}
                    className="button icon-button close-button pos-rel top-0 right-0"
                  >
                    <span className="icon minus-icon icon-size-16"></span>
                  </button>
                </div>
                <SubactionHeader text="Recording name" />
                <div class="items-center gap-1 flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block">
                  <span className="icon file-icon icon-size-16"></span>
                  <button class="overflow-hidden flex-1 flex input-with-unit button sm dropdown">
                    <span class="text-nowrap value-label text md">
                      Subfolder_name
                    </span>
                  </button>
                  {/* minus or remove buttoons top-right */}
                </div>
                <ToggleComponent
                  text="Timestamp prefix"
                  className=""
                  iconClass=""
                  isToggled={timeStampPrefix}
                  onToggle={settimeStampPrefix}
                />
                <ToggleComponent
                  text="Auto increment"
                  className=""
                  iconClass=""
                  isToggled={AutoIncrement}
                  onToggle={setAutoIncrement}
                />
                <div
                  className={clsx(
                    "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                    { disabled: !AutoIncrement }
                  )}
                >
                  <div className="gap-1 text-container overflow-hidden flex items-center">
                    <span className="icon icon-size-16 subcat-icon"></span>
                    <p className="text text-nowrap text-left md">Number</p>
                  </div>
                  <ValueSelector
                    unit=""
                    min={1}
                    max={99999}
                    initialValue={AutoIncrementValue}
                    onChange={setAutoIncrementValue}
                  />
                </div>
              </div>
            </div>
            <div className="p-1 g-1">
              <p className="text bg-md text-left">
                Camera views may lag at higher settings. Try lowering the
                resolution/reducing the number of cameras. fix is coming soon.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default CaptureLive;
