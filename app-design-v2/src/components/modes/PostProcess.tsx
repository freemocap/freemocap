import React, { useState, useEffect } from "react";
import {
  ButtonSm,
  ToggleComponent,
  ToggleButtonComponent,
  SegmentedControl,
  ValueSelector,
  SubactionHeader,
  NameDropdownSelector,
} from "../uicomponents";
import clsx from "clsx";
import ThreeDScene from "../ThreeDScene";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";

// ------------------ PostProcess UI ------------------
const PostProcess = () => {
  const HandleImportVideos = () => {
    console.log("Starting post-process…");
    setTimeout(() => console.log("Import videos button clicked"));
  };
  // Calibration & toggles
  const [skipCalibration, setSkipCalibration] = useState(true);
  const [isMultiprocessing, setIsMultiprocessing] = useState(true);
  const [maxCoreCount, setMaxCoreCount] = useState(false);

  const [charucoSize, setCharucoSize] = useState(10);

  const [selectedValue, setSelectedValue] = useState(10);

  const [selectedBufferPercentage, setselectedBufferPercentage] = useState(30);

  useEffect(() => {
    if (!isMultiprocessing) setMaxCoreCount(false);
  }, [isMultiprocessing]);

  const ModelSize = () => {
    // State for each dropdown
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

  const [isYoloCrop, setIsYoloCrop] = useState(true);

  useEffect(() => {
    // You could do extra logic here if needed
  }, [isYoloCrop]);

  const [runReprojectionFilter, setRunReprojectionFilter] = useState(true);

  const [ThresholdValue, setThresholdValue] = useState(30);

  const [RequiredCameras, setRequiredCameras] = useState(3);


  const [ButterworthFilter, setButterworthFilter] = useState(true);

  const [FrameRateValue, setFrameRateValue] = useState(30);

  const [CutOffSequence, setCutOffSequence] = useState(3);

  const [OrderValue, setOrderValue] = useState(3);

  
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
              onClick={HandleImportVideos}
            />
          </div>
        </div>

        <div className="reveal fadeIn visualize-container overflow-hidden flex-row flex gap-2 flex-3 flex-start">
          {/* Video Container */}
          <div className="align-content-start align-start video-container overflow-y flex flex-row flex-wrap gap-2 flex-3 flex-start h-full">
            {[...Array(6)].map((_, idx) => (
              <div
                key={idx}
                className="video-tile video-source size-1 bg-middark br-2 empty"
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
        <div className="br-1 bg-darkgray subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
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
            {/* subcat-header-container */}
            <SubactionHeader text="2d image trackers" />
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
                initialValue={selectedValue}
                onChange={(val) => setSelectedValue(val)}
              />
            </div>
          </div>
          <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
            <SubactionHeader text="3d triangulation methods" />
            <ToggleComponent
              text="Run 3d triangulation"
              className=""
              iconClass=""
            />
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
                <p className="text text-nowrap text-left md">Threshold (%)</p>
              </div>
              <ValueSelector
                unit="%"
                min={0}
                max={100}
                initialValue={ThresholdValue}
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
                initialValue={RequiredCameras}
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
              isToggled={ButterworthFilter}
              onToggle={setButterworthFilter}
            />

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !ButterworthFilter }
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
                initialValue={FrameRateValue}
                onChange={setFrameRateValue}
              />
            </div>

            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !ButterworthFilter}
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
                initialValue={CutOffSequence}
                onChange={setCutOffSequence}
              />
            </div>
            <div
              className={clsx(
                "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
                { disabled: !ButterworthFilter}
              )}
            >
              <div className="gap-1 text-container overflow-hidden flex items-center">
                <span className="icon icon-size-16 subcat-icon"></span>
                <p className="text text-nowrap text-left md">
                  Order
                </p>
              </div>
              <ValueSelector
                unit=""
                min={1}
                max={7}
                initialValue={OrderValue}
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
