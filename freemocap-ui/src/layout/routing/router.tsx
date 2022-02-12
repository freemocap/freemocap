import React from 'react';
import {Route, Routes} from "react-router-dom";
import {WebcamStreamCapture} from "../../views/Capture";
import {ConfigView} from "../../views/Config";
import {WebcamJonTest} from "../../views/WebcamJonTest";
import {PythonToJsTest} from "../../views/PythonToJsTest";

export const Router = () => {
  return (
    <Routes>
      <Route path={'/'} element={<React.Fragment />} />
      <Route path={'/show_cameras'} element={<WebcamStreamCapture />} />
      <Route path={'/config'} element={<ConfigView />} />
      <Route path={'/jontestplayground'} element={<WebcamJonTest />} />
      <Route path={'/pythonToJs'} element={<PythonToJsTest />} />
    </Routes>
  )
}