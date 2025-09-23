import React, { useState } from "react";
import CaptureLive from "../modes/CaptureLive";
import PostProcess from "../modes/PostProcess";
import { SegmentedControl } from "../uicomponents";

const ModePanel = () => {
  const [mode, setMode] = useState("Capture Live");
  const handleMode = (selected: string) => {
    setMode(selected);
  };

  return (
    <div className="main-container gap-1 overflow-hidden flex flex-row flex-1">
      <SegmentedControl
      className="main-segmented-control"
        options={[
          { label: "Capture Live", value: "Capture Live" },
          { label: "Post-process", value: "Post-process" },
        ]}
        size="md"
        value={mode}
        onChange={handleMode}
      />

      {mode === "Capture Live" && <CaptureLive />}
      {mode === "Post-process" && <PostProcess />}
    </div>
  );
};

export default ModePanel;
