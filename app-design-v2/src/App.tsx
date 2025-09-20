import { useState } from "react";
import reactLogo from "./assets/react.svg";
import viteLogo from "/vite.svg";
import React from "react";
import "./App.css";
import SplashModal from "./components/SplashModal"; // imported modal
import {
  ButtonSm,
  SegmentedControl,
  ToggleComponent,
  DropdownButton,
} from "./components/uicomponents";

function App() {

 // 👇 add this state here
  const [isMultiprocessing, setIsMultiprocessing] = useState(true);

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
          <ButtonSm
            iconClass="loader-icon" // Connected-icon || loader-icon || warning-icon
            text="Connecting..."
            rightSideIcon="dropdown" // dropdown || externallink || ""
            textColor="text-gray" // text-white || text-gray
            onClick={() => {
              // Developers: Replace this with navigation to community page
              console.log("Connect clicked");
            }}
          />
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
          <div className="header-tool-bar br-2">
            <SegmentedControl
              options={[
                { label: "Capture Live", value: "Capture Live" },
                { label: "Post-process", value: "Post-process" },
              ]}
              size="md"
              value={mode}
              onChange={handleMode}
            />
          </div>

          {/* visualize-container */}
          <div className="visualize-container overflow-hidden flex gap-2 flex-3">
            {/* 3d-container */}
            <div className="3d-container flex-15 bg-middark br-2" />

            {/* video-container */}
            <div className="video-container overflow-y flex flex-col gap-2 flex-15">
              <div className="flex-1 bg-middark br-2" />
              <div className="flex-1 bg-middark br-2" />
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
              />
            </div>
            <div className="flex flex-col record-container br-1 p-1 gap-1 bg-middark">
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
            </div>
          </div>
          <div className="subaction-container properties-container flex-1 br-1 p-1 gap-1 bg-darkgray">
            <ToggleComponent
              text="Run 2d image tracking"
              className=""
              iconClass=""
            />

             <ToggleComponent
          text="Multiprocessing"
          defaultToggelState={true}
          isToggled={isMultiprocessing}
          onToggle={setIsMultiprocessing}
        />

        {isMultiprocessing && (
          <ToggleComponent
            text="Max core count"
            iconClass="subcat-icon"
          />
        )}

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
