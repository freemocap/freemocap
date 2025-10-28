import React, { useState, useEffect } from "react";
import { Provider } from "react-redux";
import SegmentedControl from "../uicomponents/SegmentedControl";

/**
 * InfoPanel Component
 * --------------------
 * A segmented control UI that toggles between 3 modes:
 *   - Logs
 *   - Recording info
 *   - File directory
 *
 * Developer Notes:
 * 1. Replace the dummy data inside `renderContent` with real data.
 * 2. Add logic to fetch logs, retrieve recording metadata, or list files.
 * 3. Keep each return block self-contained for clarity and easier maintenance.
 * 4. Styling classes (Tailwind) can be extended or themed based on app design.
 */

const InfoPanel: React.FC = () => {
  const [infoMode, setInfoMode] = useState("Logs");

  const renderContent = () => {
    switch (infoMode) {
      case "Logs":
        return (
          <div className="Logs flex flex-col p-2 gap-1">
            <p className="text-sm">Dummy Log #1 - Started process...</p>
            <p className="text-sm">Dummy Log #2 - Processing data...</p>
            <p className="text-sm">Dummy Log #3 - Finished successfully.</p>
          </div>
        );
      case "Recording info":
        return (
          <div className="Recording-info flex flex-col p-2 gap-1">
            <p className="text-sm">Recording ID: 12345</p>
            <p className="text-sm">Duration: 3m 42s</p>
            <p className="text-sm">Status: Completed</p>
          </div>
        );
      case "File directory":
        return (
          <div className="File-directory flex flex-col p-2 gap-1">
            <p className="text-sm">/user/files/example1.mp4</p>
            <p className="text-sm">/user/files/example2.wav</p>
            <p className="text-sm">/user/files/example3.txt</p>
          </div>
        );
      default:
        return <div className="p-2">No content available.</div>;
    }
  };

  return (
    <div className="gap-2 overflow-hidden bottom-info-container bg-middark border-mid-black h-100 p-1 border-1 border-black br-2 flex flex-col">
      {/* Header with segmented control */}
      <div className="info-header-control h-25 bg-middark">
        <SegmentedControl
          options={[
            { label: "Logs", value: "Logs" },
            { label: "Recording info", value: "Recording info" },
            { label: "File directory", value: "File directory" },
          ]}
          size="sm"
          value={infoMode}
          onChange={(val) => setInfoMode(val)}
        />
      </div>

      {/* Dynamic content container */}
      <div className="overflow-y info-container flex flex-col flex-1 br-2 p-1 gap-1">
        {renderContent()}
      </div>
    </div>
  );
};

export default InfoPanel;
