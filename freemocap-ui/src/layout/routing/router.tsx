import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ShowCameras} from "../../views/ShowCameras";

export const Router = () => {
  return (
    <Routes>
      <Route path={'/'} element={<React.Fragment />} />
      <Route path={'/show_cameras'} element={<ShowCameras />} />
    </Routes>
  )
}