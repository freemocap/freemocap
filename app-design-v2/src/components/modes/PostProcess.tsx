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

  useEffect(() => {
    if (!isMultiprocessing) setMaxCoreCount(false);
  }, [isMultiprocessing]);
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
        <div className="subaction-container properties-container flex-1 br-1 p-1 gap-2 bg-darkgray">
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
          />
          <div class="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25  ">
            <div class="gap-1 text-container overflow-hidden flex items-center">
              <span class="icon icon-size-16 subcat-icon"></span>
              <p class="text text-nowrap text-left md">Model size</p>
            </div>
            <ValueSelector
              unit="mm"
              initialValue={selectedValue}
              onChange={(val) => setSelectedValue(val)}
            />
          </div>
          <div class="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25  ">
            <div class="gap-1 text-container overflow-hidden flex items-center">
              <span class="icon icon-size-16 subcat-icon"></span>
              <p class="text text-nowrap text-left md">Buffer bounding box</p>
            </div>
            <ValueSelector
              unit="mm"
              initialValue={selectedValue}
              onChange={(val) => setSelectedValue(val)}
            />
          </div>
          <div class="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25  ">
            <div class="gap-1 text-container overflow-hidden flex items-center">
              <span class="icon icon-size-16 subcat-icon"></span>
              <p class="text text-nowrap text-left md">Buffer percentage</p>
            </div>
            <ValueSelector
              unit="mm"
              initialValue={selectedValue}
              onChange={(val) => setSelectedValue(val)}
            />
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default PostProcess;
