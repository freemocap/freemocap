import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

import React from "react";
import "./App.css";

function App() {
  return (
    <div className="flex flex-col h-full border-2 rounded-lg overflow-hidden">
      {/* Top Red Bar */}
      <div className="bg-red h-40" />

      {/* Main Content */}
      <div className="flex flex-col flex-1">
        {/* Blue header */}
        <div className="bg-blue h-30 m-1 rounded-md" />

        {/* Body */}
        <div className="flex flex-1 p-1 gap-2">
          {/* Left + Middle group */}
          <div className="flex gap-2 flex-3">
            {/* Left panel */}
            <div className="flex-15 bg-black rounded-md" />

            {/* Middle stacked */}
            <div className="flex flex-col gap-2 flex-15">
              <div className="flex-1 bg-black rounded-md" />
              <div className="flex-1 bg-black rounded-md" />
            </div>
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-2 flex-1">
            <div className="flex-1 bg-pink rounded-md" />
            <div className="flex-1 bg-pink rounded-md" />
          </div>
        </div>
      </div>

      {/* Bottom section (with top bar inside) */}
      <div className="h-100 m-1 border-2 rounded-md flex flex-col">
        <div className="h-25 border-b-2" />
        <div className="flex-1 rounded-md" />
      </div>
    </div>
  );
}

export default App;