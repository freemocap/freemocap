import React, { useState, useEffect, useRef } from "react";
import clsx from "clsx";

import NameDropdownSelector from "../uicomponents/NameDropdownSelector";
import ButtonSm from "../uicomponents/ButtonSm";
import Checkbox from "../uicomponents/Checkbox";
import ToggleComponent from "../uicomponents/ToggleComponent";
import ValueSelector from "../uicomponents/ValueSelector";
import SubactionHeader from "../uicomponents/SubactionHeader";
import TextSelector from "../uicomponents/TextSelector";
import { STATES } from "../uicomponents/states";

import FileDirectorySettingsModal from "../FileDirectorySettingsModal";
import ThreeDScene from "../ThreeDScene";

// ------------------ PostProcess UI ------------------
const PostProcess: React.FC = () => {
  // --- Modal and Directory States ---
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [directoryPath, setDirectoryPath] = useState(
    "C:\\Users\\pooyadeperson.com"
  );
  const [timeStampPrefix, setTimeStampPrefix] = useState(false);
  const [autoIncrement, setAutoIncrement] = useState(false);
  const [autoIncrementValue, setAutoIncrementValue] = useState(3);

  const wrapperRef = useRef<HTMLDivElement | null>(null);

  // Handle outside click to close modal
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
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

  const handleImportVideos = () => {
    console.log("Starting post-process…");
    setTimeout(() => console.log("Import videos button clicked"));
  };

  // Calibration & toggles
  const [skipCalibration, setSkipCalibration] = useState(true);
  const [isMultiprocessing, setIsMultiprocessing] = useState(true);
  const [maxCoreCount, setMaxCoreCount] = useState(false);

  const [charucoSize, setCharucoSize] = useState(10);

  const [selectedValue, setSelectedValue] = useState(10);

  const [selectedBufferPercentage, setSelectedBufferPercentage] =
    useState(30);

  useEffect(() => {
    if (!isMultiprocessing) setMaxCoreCount(false);
  }, [isMultiprocessing]);

  const ModelSize: React.FC = () => {
    const [selectedModel1, setSelectedModel1] = useState("Nano");
    const options = ["Nano", "Medium", "Large"];

    return (
      <div className="flex flex-col">
        <div className="dropdown-container">
          <NameDropdownSelector
            options={options}
            initialValue={selectedModel1}
            onChange={setSelectedModel1}
          />
        </div>
      </div>
    );
  };

  const ModelComplexity: React.FC = () => {
    const [selectedModel1, setSelectedModel1] =
      useState("Fastest, Loose");
    const options = [
      "Fastest, Loose",
      "Medium, Balanced",
      "Slowest, Precise",
    ];

    return (
      <div className="flex flex-col">
        <div className="dropdown-container">
          <NameDropdownSelector
            options={options}
            initialValue={selectedModel1}
            onChange={setSelectedModel1}
          />
        </div>
      </div>
    );
  };

  const [isYoloCrop, setIsYoloCrop] = useState(true);

  const [runReprojectionFilter, setRunReprojectionFilter] =
    useState(true);

  const [thresholdValue, setThresholdValue] = useState(30);

  const [requiredCameras, setRequiredCameras] = useState(3);

  const [butterworthFilter, setButterworthFilter] = useState(true);

  const [frameRateValue, setFrameRateValue] = useState(30);

  const [cutOffSequence, setCutOffSequence] = useState(3);

  const [orderValue, setOrderValue] = useState(3);

  const [minDetectionConfidence, setMinDetectionConfidence] =
    useState(0.5);

  const [minTrackingConfidence, setMinTrackingConfidence] =
    useState(0.5);

  const [staticImageMode, setStaticImageMode] = useState(true);

  return (
    <>
      <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
        <div className="flex flex-row header-tool-bar br-2 gap-4">
          <div className="reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex ">
            <ButtonSm
              iconClass="import-icon"
              text="Import videos"
              buttonType=""
              rightSideIcon=""
              textColor="text-white"
              onClick={handleImportVideos}
            />
          </div>
        </div>

        <div className="reveal fadeIn visualize-container overflow-hidden flex-row flex gap-2 flex-3 flex-start">
          {/* Video Container */}
          <div className="align-content-start align-start video-container overflow-y flex flex-row flex-wrap gap-2 flex-3 flex-start h-full mt-1">
            {[...Array(6)].map((_, idx) => (
              <div
                key={idx}
                className="video-tile video-source size-2 bg-middark br-2 empty"
              />
            ))}
          </div>
          {/* 3D Scene Container */}
          <div className="overflow-hidden 3D-container br-2 flex flex-row flex-wrap gap-2 flex-2 flex-start bg-middark h-full">
            <ThreeDScene />
          </div>
        </div>
      </div>

      <div className="reveal fadeIn action-container flex-1 bg-darkgray br-2 border-mid-black border-1 min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
        <div className="z-2 subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
          <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
            <SubactionHeader text="File location" />
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
                onSelectSubfolder={setSubfolderName}
                onRemoveSubfolder={handleRemoveSubfolder}
                recordingName="Recording1"
                onSelectRecordingName={() =>
                  console.log("Select recording name clicked")
                }
                timeStampPrefix={timeStampPrefix}
                setTimeStampPrefix={setTimeStampPrefix}
                autoIncrement={autoIncrement}
                setAutoIncrement={setAutoIncrement}
                autoIncrementValue={autoIncrementValue}
                setAutoIncrementValue={setAutoIncrementValue}
              />
            </div>
          </div>
        </div>

        <div className="br-1 bg-darkgray subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
          <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
            {/* text input container numeric value */}
            <div className="text-input-container gap-1 br-1 flex justify-content-space-between items-center h-25">
              <div className="text-container overflow-hidden flex items-center">
                {/* explainer icon */}
                <button
                  onClick={() => {}}
                  className="button icon-button close-button"
                >
                  <span className="icon explainer-icon icon-size-16"></span>
                </button>

                <p className="text text-nowrap text-left md">Charuco size</p>
              </div>
              <ValueSelector
                unit="mm"
                min={1}
                max={999}
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
            <ButtonSm
              iconClass="processmocap-icon"
              text="Process Mocap"
              buttonType="full-width primary justify-center"
              rightSideIcon=""
              textColor="text-white"
              onClick={() => console.log("Mocap process clicked")}
            />
            <div className="p-1 g-1">
              <p className="text bg-md text-left">
                Install Blender and enable the Rigify add-on for more accurate
                mocap results. learn more
              </p>
            </div>
          </div>
        </div>

        <div className="subaction-container overflow-y properties-container flex-1 br-1 p-1 gap-2 bg-darkgray">
          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="2d image trackers" />
            <ToggleComponent text="Run 2d image tracking" className="" iconClass="" />
            <ToggleComponent
              text="Multiprocessing"
              defaultToggelState={true}
              isToggled={isMultiprocessing}
              onToggle={setIsMultiprocessing}
            />
            <ToggleComponent
              text="Max core count"
              iconClass="subcat-icon"
              isToggled={maxCoreCount}
              onToggle={setMaxCoreCount}
              disabled={!isMultiprocessing}
              className={!isMultiprocessing ? "disabled" : ""}
            />
          </div>

          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="Mediapipe" />
            <ToggleComponent
              text="Yolo crop mode"
              className=""
              iconClass=""
              defaultToggelState={true}
              isToggled={isYoloCrop}
              onToggle={setIsYoloCrop}
            />

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !isYoloCrop }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">Model size</p>
              </div>
              <ModelSize />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !isYoloCrop }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">
                  Buffer bounding box
                </p>
              </div>
              <ValueSelector
                unit=""
                initialValue={selectedValue}
                onChange={(val) => setSelectedValue(val)}
              />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !isYoloCrop }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">
                  Buffer percentage
                </p>
              </div>
              <ValueSelector
                unit="%"
                min={0}
                max={100}
                initialValue={selectedBufferPercentage}
                onChange={(val) => setSelectedBufferPercentage(val)}
              />
            </div>

            <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <p className="text text-nowrap text-left md">Model complexity</p>
              </div>
              <ModelComplexity />
            </div>

            <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <p className="text text-nowrap text-left md">
                  Min detection confidence
                </p>
              </div>
              <ValueSelector
                unit=""
                min={0}
                max={1}
                initialValue={minDetectionConfidence}
                onChange={(val) => setMinDetectionConfidence(val)}
              />
            </div>

            <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <p className="text text-nowrap text-left md">
                  Min tracking confidence
                </p>
              </div>
              <ValueSelector
                unit=""
                min={0}
                max={1}
                initialValue={minTrackingConfidence}
                onChange={(val) => setMinTrackingConfidence(val)}
              />
            </div>

            <ToggleComponent
              text="Static image mode"
              className=""
              iconClass=""
              defaultToggelState={true}
              isToggled={staticImageMode}
              onToggle={setStaticImageMode}
            />
          </div>

          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="3d triangulation methods" />
            <ToggleComponent text="Run 3d triangulation" className="" iconClass="" />
          </div>

          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="Anipose triangulation" />
            <ToggleComponent text="RANSAC method" className="" iconClass="" />
            <ToggleComponent
              text="Flatten single camera data"
              className=""
              iconClass=""
            />
          </div>

          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="Reprojection error filtering" />
            <ToggleComponent
              text="Run reprojection error filtering"
              className=""
              iconClass=""
              defaultToggelState={true}
              isToggled={runReprojectionFilter}
              onToggle={setRunReprojectionFilter}
            />

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !runReprojectionFilter }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">Threshold</p>
              </div>
              <ValueSelector
                unit="%"
                min={0}
                max={100}
                initialValue={thresholdValue}
                onChange={setThresholdValue}
              />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !runReprojectionFilter }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">
                  Required cameras
                </p>
              </div>
              <ValueSelector
                unit=""
                min={0}
                max={20}
                initialValue={requiredCameras}
                onChange={setRequiredCameras}
              />
            </div>
          </div>

          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="Post processing data cleanup" />
            <ToggleComponent
              text="Butterworth filter"
              className=""
              iconClass=""
              defaultToggelState={true}
              isToggled={butterworthFilter}
              onToggle={setButterworthFilter}
            />

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !butterworthFilter }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">Framerate</p>
              </div>
              <ValueSelector
                unit="FPS"
                min={30}
                max={120}
                initialValue={frameRateValue}
                onChange={setFrameRateValue}
              />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !butterworthFilter }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">
                  Cutoff frequence
                </p>
              </div>
              <ValueSelector
                unit=""
                min={1}
                max={7}
                initialValue={cutOffSequence}
                onChange={setCutOffSequence}
              />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !butterworthFilter }
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">Order</p>
              </div>
              <ValueSelector
                unit=""
                min={1}
                max={7}
                initialValue={orderValue}
                onChange={setOrderValue}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default PostProcess;
