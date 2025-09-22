import {Provider} from 'react-redux';
// import AppLayout from "./components/layout/AppLayout.tsx";
import {store} from "./store";
import { useState, useEffect } from "react";
import reactLogo from "./assets/react.svg";
import viteLogo from "/vite.svg";
import React from "react";
import "./App.css";
import { ButtonSm, DropdownButton } from "./components/primitives/Buttons/ButtonSm";
// import { DropdownButton } from "./components/composites/DropdownButton";
import SplashModal from "./components/SplashModal"; // imported modal
import {
  SegmentedControl,
  // ToggleComponent,
  // DropdownButton,
  ToggleButtonComponent,
  ConnectionDropdown,
  StandaloneToggleExample,
} from "./components/uicomponents";

function App() {

  const [streamState, setStreamState] = useState("disconnected"); // <-- FIX
  // /* stream connnection logic */
  // const handleConnect = () => {
  //   // 🔌 TODO: Replace with your real "connect" logic
  //   console.log("Connected!");
  // };

  // const handleDisconnect = () => {
  //   // 🔌 TODO: Replace with your real "disconnect" logic
  //   console.log("Disconnected!");
  // };

  // state for show and hide record if skip calibration is turned off or on
  const [skipCalibration, setSkipCalibration] = useState(true); // default true

  const [isMultiprocessing, setIsMultiprocessing] = useState(true);
  const [maxCoreCount, setMaxCoreCount] = useState(false); // local state

  useEffect(() => {
    if (!isMultiprocessing) setMaxCoreCount(false);
  }, [isMultiprocessing]);

  const [showSplash, setShowSplash] = useState(true); // modal state

  const [mode, setMode] = useState("Capture Live");
  // Handler for the first segmented control .. main modes
  const handleMode = (selected) => {
    setMode(selected);
    console.log("User selected mode:", selected);
    // Add your logic for the first segmented control here
  };

  const [infoMode, setInfoMode] = useState("Logs"); // <-- added state
  // Handler for the second segmented control .. info container mode
  const handleInfoMode = (selected) => {
    setInfoMode(selected);
    console.log("User selected info mode:", selected);
    // Add your logic for the second segmented control here
  };

  return (
    <div className="app-content bg-middark flex flex-col p-1 gap-1 h-full overflow-hidden">
      {/* splash modal */}
      {showSplash && <SplashModal onClose={() => setShowSplash(false)} />}

      {/* top-header */}
      <div className="flex flex-row justify-content-space-between top-header br-2 h-25">
        <div className="flex left-section">
          {/* <ButtonSm
            iconClass="loader-icon" // Connected-icon || loader-icon || warning-icon
            text="Connecting..."
            rightSideIcon="dropdown" // dropdown || externallink || ""
            textColor="text-gray" // text-white || text-gray
            onClick={() => {
              // Developers: Replace this with navigation to community page
              console.log("Connect clicked");
            }}
          /> */}
          <ConnectionDropdown />
        </div>
        <div className="flex right-section gap-2">
          <ButtonSm
            iconClass="donate-icon"
            text="Support the freemocap"
            rightSideIcon="externallink"
            textColor="text-gray"
            onClick={() => {
              // Developers: Replace this with navigation or tutorial logic
              console.log("Support freemocap clicked");
            }}
          />

          <DropdownButton
            containerClassName="align-end"
            buttonProps={{
              text: "Help",
              rightSideIcon: "dropdown",
              textColor: "text-gray",
              iconClass: "",
              
              onClick: () => console.log("help dropdown button clicked"),
            }}
            dropdownItems={[
              <ButtonSm
                key="FreeMocap Guide"
                rightSideIcon="externallink"
                buttonType="full-width"
                text="FreeMocap Guide"
                iconClass="learn-icon"
                onClick={() => console.log("FreeMocap Guide clicked")}
              />,
              <ButtonSm
                key="Ask Question on Discord"
                rightSideIcon="externallink"
                buttonType="full-width"
                text="Ask Question on Discord"
                iconClass="discord-icon"
                onClick={() => console.log("Ask Question on Discord clicked")}
              />,
              <ButtonSm
                key="tutorials"
                buttonType="full-width"
                text="Download Sample Videos"
                iconClass="download-icon"
                onClick={() => console.log("Download Sample Videos clicked")}
              />,
            ]}
          />
        </div>
      </div>

      {/* main-container */}
      <div className="main-container gap-1 overflow-hidden flex flex-row flex-1">
        {/* mode-container */}
        <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 .bg-darkgray overflow-hidden flex flex-col flex-1 gap-1 p-1">
          {/* header-tool-bar */}
          <div className="flex flex-row header-tool-bar br-2 gap-4">
            <SegmentedControl
              options={[
                { label: "Capture Live", value: "Capture Live" },
                { label: "Post-process", value: "Post-process" },
              ]}
              size="md"
              value={mode}
              onChange={handleMode}
            />
            <div className="active-tools-header br-1-1 gap-1 p-1 flex ">
              <ToggleButtonComponent
  state={streamState}  // <-- controlled state
  connectConfig={{
    text: "Stream",
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
    text: "Streaming",
    iconClass: "streaming-icon",
    rightSideIcon: "",
    extraClasses: "activated",
  }}
  textColor="text-white"
  onConnect={() => {
    console.log("Checking before streaming…");
    setStreamState("connecting");
    setTimeout(() => setStreamState("connected"), 2000);
  }}
  onDisconnect={() => {
    console.log("Stopped streaming!");
    setStreamState("disconnected");
  }}
/>
            </div>
          </div>

          {/* visualize-container */}
          <div className="visualize-container overflow-y flex gap-2 flex-3 flex-start">
            {/* 3d-container */}
            {/* <div className="3d-visualizer-container flex-15 bg-middark br-2" /> */}

            {/* video-container */}
            <div className="video-container flex flex-row flex-wrap gap-2 flex-1 flex-start">
              <div className="video-tile size-1 bg-middark br-2 empty" />
              <div className="video-tile size-1 bg-middark br-2 empty" />
              <div className="video-tile size-1 bg-middark br-2 empty" />
              <div className="video-tile size-1 bg-middark br-2 empty" />
              <div className="video-tile size-1 bg-middark br-2 empty" />
              <div className="video-tile size-1 bg-middark br-2 empty" />
            </div>
          </div>
        </div>

        {/* action container */}
        <div className="action-container flex-1 overflow-y bg-darkgray br-2 border-mid-black border-1 .bg-darkgray overflow-y min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
          <div className="subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
            <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
              <ToggleComponent text="Charuco size" className="" iconClass="" />
              <ButtonSm
                iconClass="calibrate-icon"
                text="Calibrate"
                buttonType="full-width secondary justify-center"
                rightSideIcon=""
                textColor="text-white"
                onClick={() => {
                  // Developers: Replace this with navigation or tutorial logic
                  console.log("help button clicked");
                }}
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
            {/* Show record-container only if skipCalibration is true */}
            {/* {skipCalibration && ( */}
            <div
              className={`flex flex-col record-container br-1 p-1 gap-1 bg-middark reveal ${
                skipCalibration ? "" : "disabled"
              }`}
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
              <ButtonSm
                iconClass="record-icon"
                text="Record"
                buttonType="full-width primary justify-center"
                rightSideIcon=""
                textColor="text-white"
                onClick={() => {
                  // Developers: Replace this with navigation or tutorial logic
                  console.log("help button clicked");
                }}
              />
              <div className="p-1 g-1">
                <p className="text bg-md text-left">
                  Camera views may lag at higher settings. Try lowering the
                  resolution/reducing the number of cameras. fix is coming soon.
                </p>
              </div>
            </div>
            {/* // )} */}
          </div>
          <div className="subaction-container properties-container flex-1 br-1 p-1 gap-1 bg-darkgray">
            <ToggleComponent
              text="Run 2d image tracking"
              className=""
              iconClass=""
            />
            {/* Parent toggle */}
            <ToggleComponent
              text="Multiprocessing"
              defaultToggelState={true}
              isToggled={isMultiprocessing}
              onToggle={setIsMultiprocessing}
            />

            {/* Dependent toggle */}
            <ToggleComponent
              text="Max core count"
              iconClass="subcat-icon"
              isToggled={maxCoreCount}
              onToggle={setMaxCoreCount}
              disabled={!isMultiprocessing} // disables interaction when parent off
              className={!isMultiprocessing ? "disabled" : ""}
            />

            <ToggleComponent
              text="Yolo crop mode"
              className=""
              iconClass=""
              defaultToggelState={true}
            />
          </div>
        </div>
      </div>

      {/* bottom info-container */}
      <div className="gap-2 overflow-hidden bottom-info-container bg-middark border-mid-black h-100 p-1 border-1 border-black br-2 flex flex-col">
        <div className="info-header-control h-25 bg-middark">
          <SegmentedControl
            options={[
              { label: "Logs", value: "Logs" },
              { label: "Recording info", value: "Recording info" },
              { label: "File directory", value: "File directory" },
            ]}
            size="sm"
            value={infoMode}
            onChange={handleInfoMode}
          />
        </div>

        <div className="overflow-y info-container flex flex-col flex-1 br-2 p-1 gap-1">
          <p className="text md text-left">
            \Users\andre\freemocap_data\logs_info_and_settings\last_successful_calibration.toml.
            [2024-01-18T23:14:32.0235][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.gui.qt.utilities.update_most_recent_recording_toml:update_most_recent_recording_toml():16]:::
            Saving most recent recording path C:
            \Users\andre\freemocap_data\recording sessions\freemocap_sample_data
            to toml file:
            C:\Users\andre\freemocap_data\logs_info_and_settings\most_recent_recording.toml.
            [2024-01-18T23:14:32.0251][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.data_layer.recording_models.recording_info_model:get_number_of_mp4s_in_synched_videos_directory():238]
            ::: Number of `.mp4''s in C:
            \Users\andre\freemocap_data\recording_sessions\freemocap_sample_data\synchronized_videos:
            3.0.\Users\andre\freemocap_data\logs_info_and_settings\last_successful_calibration.toml.
            [2024-01-18T23:14:32.0235][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.gui.qt.utilities.update_most_recent_recording_toml:update_most_recent_recording_toml():16]:::
            Saving most recent recording path C:
            \Users\andre\freemocap_data\recording sessions\freemocap_sample_data
            to toml file:
            C:\Users\andre\freemocap_data\logs_info_and_settings\most_recent_recording.toml.
            [2024-01-18T23:14:32.0251][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.data_layer.recording_models.recording_info_model:get_number_of_mp4s_in_synched_videos_directory():238]
            ::: Number of `.mp4''s in C:
            \Users\andre\freemocap_data\recording_sessions\freemocap_sample_data\synchronized_videos:
            3.0.\Users\andre\freemocap_data\logs_info_and_settings\last_successful_calibration.toml.
            [2024-01-18T23:14:32.0235][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.gui.qt.utilities.update_most_recent_recording_toml:update_most_recent_recording_toml():16]:::
            Saving most recent recording path C:
            \Users\andre\freemocap_data\recording sessions\freemocap_sample_data
            to toml file:
            C:\Users\andre\freemocap_data\logs_info_and_settings\most_recent_recording.toml.
            [2024-01-18T23:14:32.0251][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.data_layer.recording_models.recording_info_model:get_number_of_mp4s_in_synched_videos_directory():238]
            ::: Number of `.mp4''s in C:
            \Users\andre\freemocap_data\recording_sessions\freemocap_sample_data\synchronized_videos:
            3.0.\Users\andre\freemocap_data\logs_info_and_settings\last_successful_calibration.toml.
            [2024-01-18T23:14:32.0235][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.gui.qt.utilities.update_most_recent_recording_toml:update_most_recent_recording_toml():16]:::
            Saving most recent recording path C:
            \Users\andre\freemocap_data\recording sessions\freemocap_sample_data
            to toml file:
            C:\Users\andre\freemocap_data\logs_info_and_settings\most_recent_recording.toml.
            [2024-01-18T23:14:32.0251][INFO ] [ProcessID: 1192, ThreadID: 22204]
            [freemocap.data_layer.recording_models.recording_info_model:get_number_of_mp4s_in_synched_videos_directory():238]
            ::: Number of `.mp4''s in C:
            \Users\andre\freemocap_data\recording_sessions\freemocap_sample_data\synchronized_videos:
            3.0.
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
