import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import React from "react";
import "./App.css";

function App() {
  return (
    <div className="app-content bg-black flex flex-col p-1 gap-1 h-full overflow-hidden">
      {/* top-header */}
      <div className="top-header br-2 h-25" />

      {/* main-container */}
      <div className="main-container gap-1 overflow-hidden flex flex-row flex-1">
        {/* mode-container */}
        <div className="mode-container br-2 bg-mid-black border-mid-black border-2 .bg-mid-black overflow-hidden flex flex-col flex-1 gap-1 p-1">
          {/* header-tool-bar */}
          <div className="header-tool-bar h-40 br-2 h-30" />

          {/* visualize-container */}
          <div className="visualize-container overflow-hidden flex gap-2 flex-3">
            {/* 3d-container  */}
            <div className="3d-container flex-15 bg-black br-2" />

            {/* video-container */}
            <div className="video-container overflow-y flex flex-col gap-2 flex-15">
              <div className="flex-1 bg-black br-2" />
              <div className="flex-1 bg-black br-2" />
            </div>
          </div>
        </div>

        {/* action container -- right right */}
        <div className="action-container overflow-y bg-mid-black br-2 border-mid-black border-2 .bg-mid-black overflow-y min-w-200 max-w-300 flex flex-col gap-1 flex-1 p-1">
          <div className="subaction-container calibrate-container flex-1 br-1 p-1 gap-1 bg-black" />
          <div className="subaction-container record-container flex-1 br-1 p-1 gap-1 bg-black" />
          <div className="subaction-container properties-container flex-1 br-1 p-1 gap-1 bg-black" />
        </div>
      </div>

      {/* bottom info-container */}
      <div className="bottom-info-container bg-black border-mid-black h-100 p-1 border-2 border-black br-2 flex flex-col">
        <div className="info-header-control h-25 bg-black" />
        <div className="info-container flex flex-col flex-1 br-2 p-1 gap-1" />  
      </div>
    </div>
  );
}

export default App;
