import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ShowCameras} from "../../views/ShowCameras";
import {WebcamStreamCapture} from "../../views/Capture";
import {ConfigView} from "../../views/Config";

export const Router = () => {
  return (
    <Routes>
      <Route path={'/'} element={<React.Fragment />} />
      <Route path={'/show_cameras'} element={<WebcamStreamCapture />} />
      <Route path={'/config'} element={<ConfigView />} />
    </Routes>
  )
}