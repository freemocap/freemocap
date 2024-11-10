import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ConfigView} from "@/views/Config";
import {BrowserCamerasView} from "@/views/BrowserCamerasView";
import {PythonToJsTest} from "@/views/PythonToJsTest";
import {BoardDetection} from "@/views/BoardDetection";
import {SkeletonDetection} from "@/views/SkeletonDetection";
import {PythonCamerasView} from "@/views/PythonCamerasView";
import {DefaultView} from "@/views/Default";

export const Router = () => {
    return (
        <Routes>
            <Route path={'/'} element={<React.Fragment/>}/>
            <Route path={'/default'} element={<DefaultView/>}/>
            <Route path={'/config'} element={<ConfigView/>}/>
            <Route path={'/jontestplayground'} element={<BrowserCamerasView/>}/>
            <Route path={'/pythonToJs'} element={<PythonToJsTest/>}/>
            {/*<Route path={'/charuco_board_detection'} element={<BoardDetection/>}/>*/}
            {/*<Route path={'/skeleton_detection'} element={<SkeletonDetection/>}/>*/}
            <Route path={'/show_cameras'} element={<PythonCamerasView/>}/>
        </Routes>
    )
}
