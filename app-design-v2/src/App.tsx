import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import React from "react";
import "./App.css";

function App() {
  return (
    <div className="flex flex-col h-full border-2 border-black br-5 overflow-hidden">
      {/* Top Red Bar */}
      <div className="bg-red h-40" />

      {/* Main Content */}
      <div className="flex flex-col flex-1">
        {/* Blue header */}
        <div className="bg-blue h-30 m-1 br-2" />

        {/* Body */}
        <div className="flex flex-1 p-1 gap-2">
          {/* Left + Middle group */}
          <div className="flex gap-2 flex-3">
            {/* Left panel */}
            <div className="flex-15 bg-black br-2" />

            {/* Middle stacked */}
            <div className="flex flex-col gap-2 flex-15">
              <div className="flex-1 bg-black br-2" />
              <div className="flex-1 bg-black br-2" />
            </div>
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-2 flex-1">
            <div className="flex-1 bg-pink br-2" />
            <div className="flex-1 bg-pink br-2" />
          </div>
        </div>
      </div>

      {/* Bottom section */}
      <div className="h-100 m-1 border-2 border-black br-2 flex flex-col">
        <div className="h-25 border-2 border-black br-2" />
        <div className="flex-1 br-2" />
      </div>
    </div>
  );
}

export default App;
