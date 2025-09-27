import React, { useState, useEffect, useRef } from "react";
import {
  ButtonSm,
  ToggleComponent,
  ToggleButtonComponent,
  ValueSelector,
  SubactionHeader,
} from "../uicomponents";
import clsx from "clsx";
import FileDirectorySettingsModal from "../FileDirectorySettingsModal";

const CaptureLive = () => {
  // -------------------- Modal state --------------------
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [directoryPath, setDirectoryPath] = useState("C:\\Users\\pooyadeperson.com");
  const [timeStampPrefix, settimeStampPrefix] = useState(false);
  const [AutoIncrement, setAutoIncrement] = useState(false);
  const [AutoIncrementValue, setAutoIncrementValue] = useState(3);

  const wrapperRef = useRef<HTMLDivElement | null>(null);

  // Handle outside click to close modal
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsModalOpen(false);
      }
    }
    if (isModalOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isModalOpen]);

  const toggleModal = () => {
    setIsModalOpen((prev) => !prev);
  };

  // -------------------- Subfolder state --------------------
  const [subfolderName, setSubfolderName] = useState("");
  const [hasSubfolder, setHasSubfolder] = useState(false);

  const handleAddSubfolder = () => {
    setSubfolderName("NewSubfolder");
    setHasSubfolder(true);
  };

  const handleRemoveSubfolder = () => {
    setSubfolderName("");
    setHasSubfolder(false);
  };

  // -------------------- Stream state --------------------
  const [streamState, setStreamState] = useState("disconnected");
  const [skipCalibration, setSkipCalibration] = useState(true);
  const [selectedValue, setSelectedValue] = useState(10);

  const handleStreamConnect = () => {
    console.log("Checking before streaming…");
    setStreamState("connecting");
    setTimeout(() => setStreamState("connected"), 2000);
  };

  const handleStreamDisconnect = () => {
    console.log("Stopped streaming!");
    setStreamState("disconnected");
  };

  // -------------------- Countdown state --------------------
  const [Countdown, setCountdown] = useState(false);
  const [CounterValue, setCounterValue] = useState(3);

  return (
    <>
      {/* mode-container */}
      <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
        <div className="flex flex-row header-tool-bar br-2 gap-4">
          {/* stream connect/disconnect button */}
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

      {/* action-container */}
      <div className="reveal fadeIn action-container flex-1 bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
        <div className="subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
          <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
            {/* numeric value input */}
            <div className="text-input-container gap-1 br-1 flex justify-content-space-between items-center h-25">
              <div className="text-container overflow-hidden flex items-center">
                <button onClick={() => {}} className="button icon-button close-button">
                  <span className="icon explainer-icon icon-size-16"></span>
                </button>
                <p className="text text-nowrap text-left md">Charuco size</p>
              </div>
              <ValueSelector
                unit="mm"
                initialValue={selectedValue}
                value={selectedValue}
                onChange={(val: number) => setSelectedValue(val)}
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
            <ToggleComponent
              text="Auto open Blender"
              className=""
              iconClass=""
              defaultToggelState={true}
            />

            {/* record controls + file directory trigger */}
            <div className="record-group flex flex-col gap-1 border-1 border-mid-black br-2 p-1 pb-2">
              <ButtonSm
                iconClass="record-icon"
                text="Record"
                buttonType="full-width primary justify-center"
                rightSideIcon=""
                textColor="text-white"
                onClick={() => console.log("Record clicked")}
              />

              {/* trigger button + modal wrapper */}
              <div className="pos-rel" ref={wrapperRef}>
                <div
                  onClick={toggleModal}
                  className="trigger-file-directory-settings overflow-hidden button modal-trigger-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25 cursor-pointer"
                >
                  <span className="folder-directory overflow-hidden text-nowrap text md">
                    {directoryPath}
                  </span>
                  <span className="subfolder-directory overflow-hidden text-nowrap text md">
                    {hasSubfolder ? subfolderName : ""}
                  </span>
                  <button className="button icon-button pos-rel top-0 right-0">
                    <span className="icon settings-icon icon-size-16"></span>
                  </button>
                </div>

                {/* Modal */}
                <FileDirectorySettingsModal
                  isOpen={isModalOpen}
                  onClose={() => setIsModalOpen(false)}
                  directoryPath={directoryPath}
                  onSelectDirectory={setDirectoryPath}
                  onAddSubfolder={handleAddSubfolder}
                  subfolderName={subfolderName}
                  hasSubfolder={hasSubfolder}
                  onSelectSubfolder={() => console.log("Select subfolder clicked")}
                  onRemoveSubfolder={handleRemoveSubfolder}
                  recordingName="Recording1"
                  onSelectRecordingName={() => console.log("Select recording name clicked")}
                  timeStampPrefix={timeStampPrefix}
                  setTimeStampPrefix={settimeStampPrefix}
                  autoIncrement={AutoIncrement}
                  setAutoIncrement={setAutoIncrement}
                  autoIncrementValue={AutoIncrementValue}
                  setAutoIncrementValue={setAutoIncrementValue}
                />
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
                  value={CounterValue}
                  onChange={setCounterValue}
                />
              </div>
            </div>

            <div className="p-1 g-1">
              <p className="text bg-md text-left">
                Camera views may lag at higher settings. Try lowering the resolution/reducing the
                number of cameras. fix is coming soon.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default CaptureLive;
