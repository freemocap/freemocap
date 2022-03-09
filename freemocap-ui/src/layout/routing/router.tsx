import React from 'react';
import {Route, Routes} from "react-router-dom";
import {WebcamStreamCapture} from "../../views/Capture";
import {ConfigView} from "../../views/Config";
import {WebcamJonTest} from "../../views/WebcamJonTest";
import {PythonToJsTest} from "../../views/PythonToJsTest";
import {BoardDetection} from "../../views/BoardDetection";
import {SkeletonDetection} from "../../views/SkeletonDetection";

export const Router = () => {
  return (
    <Routes>
      <Route path={'/'} element={<React.Fragment />} />
      <Route path={'/show_cameras'} element={<WebcamStreamCapture />} />
      <Route path={'/config'} element={<ConfigView />} />
      <Route path={'/jontestplayground'} element={<WebcamJonTest />} />
      <Route path={'/pythonToJs'} element={<PythonToJsTest />} />
      <Route path={'/board_detection'} element={<BoardDetection />} />
      <Route path={'/skeleton_detection'} element={<SkeletonDetection />} />
    </Routes>
  )
}