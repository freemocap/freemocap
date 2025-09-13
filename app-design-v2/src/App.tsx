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
      <div className="main-container overflow-hidden flex flex-row flex-1">
        {/* mode-container */}
        <div className="mode-container border-mid-black border-1 .bg-mid-black overflow-hidden flex flex-col flex-1 gap-1 p-1">
          {/* header-tool-bar */}
          <div className="header-tool-bar h-40 br-2 h-30" />

          {/* visualize-container */}
          <div className="visualize-container flex gap-2 flex-3">
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
        <div className="action-container border-mid-black border-1 .bg-mid-black overflow-y min-w-200 max-w-300 flex flex-col gap-1 flex-1 p-1">
          <div className="flex-1 bg-pink br-2" />
          <div className="flex-1 bg-pink br-2" />
        </div>
      </div>

      {/* bottom info-container */}
      <div className="bottom-info-container h-100 m-1 border-2 border-black br-2 flex flex-col">
        <div className="info-header-control h-25 border-2 border-black br-2" />
        <div className="info-container flex-1 br-2" />  
      </div>
    </div>
  );
}

export default App;
