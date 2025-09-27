import React, { useState, useEffect } from "react";

// Extend the Window interface to include showDirectoryPicker
declare global {
  interface Window {
    showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>;
  }
}

import {
  ToggleComponent,
  ValueSelector,
  SubactionHeader,
} from "./uicomponents";
import clsx from "clsx";

interface FileDirectorySettingsModalProps {
  isOpen: boolean;
  onClose: () => void;

  // Directory
  directoryPath: string;
  onSelectDirectory: (path: string) => void;
  onAddSubfolder: () => void;

  // Subfolder
  subfolderName: string;
  hasSubfolder: boolean;
  onSelectSubfolder: () => void;
  onRemoveSubfolder: () => void;

  // Recording name
  recordingName: string;
  onSelectRecordingName: () => void;

  // Toggles
  timeStampPrefix: boolean;
  setTimeStampPrefix: (value: boolean) => void;
  autoIncrement: boolean;
  setAutoIncrement: (value: boolean) => void;

  // Auto increment value
  autoIncrementValue: number;
  setAutoIncrementValue: (value: number) => void;
}

const FileDirectorySettingsModal: React.FC<FileDirectorySettingsModalProps> = ({
  isOpen,
  onClose,

  directoryPath,
  onSelectDirectory,
  onAddSubfolder,

  subfolderName,
  hasSubfolder,
  onSelectSubfolder,
  onRemoveSubfolder,

  recordingName,
  onSelectRecordingName,

  timeStampPrefix,
  setTimeStampPrefix,
  autoIncrement,
  setAutoIncrement,

  autoIncrementValue,
  setAutoIncrementValue,
}) => {
  const [showSubfolder, setShowSubfolder] = useState(false);
  const [formattedTimestamp, setFormattedTimestamp] = useState("");

  const getFormattedTimestamp = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");
    return `${year}-${month}-${day}_${hours}-${minutes}-${seconds}\u00A0`;
  };

  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    if (timeStampPrefix) {
      setFormattedTimestamp(getFormattedTimestamp());
      intervalId = setInterval(() => {
        setFormattedTimestamp(getFormattedTimestamp());
      }, 1000);
    }
    return () => {
      clearInterval(intervalId);
    };
  }, [timeStampPrefix]);

  const handleAddSubfolder = () => {
    onAddSubfolder();
    setShowSubfolder(true);
  };

  const handleSelectDirectory = async () => {
    if (window.electronAPI) {
      const path = await window.electronAPI.selectDirectory();
      if (path) {
        onSelectDirectory(path);
      }
    } else if (window.showDirectoryPicker) {
      // Modern web API for directory selection
      try {
        const directoryHandle = await window.showDirectoryPicker();
        onSelectDirectory(directoryHandle.name);
      } catch (error) {
        console.error("Error selecting directory:", error);
      }
    } else {
      // Fallback for older browsers
      console.log("Your browser does not support modern directory selection. Using fallback.");
      const input = document.createElement("input");
      input.type = "file";
      input.webkitdirectory = true;
      input.onchange = (event: any) => {
        const files = event.target.files;
        if (files.length > 0) {
          const path = files[0].webkitRelativePath.split("/")[0];
          onSelectDirectory(path);
        }
      };
      input.click();
    }
  };

  const handleRemoveSubfolder = () => {
    onRemoveSubfolder();
    setShowSubfolder(false);
  };

  if (!isOpen) return null;

  return (
    <div className="file-directory-settings-modal modal border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1">
      <div className="flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
        {/* Directory */}
        <SubactionHeader text="Recording directory" />
        <div className="flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block gap-1">
          <button
            onClick={handleSelectDirectory}
            className="overflow-hidden flex-1 flex input-with-unit button sm select-folder gap-1"
          >
            <span className="folder-directory overflow-hidden text-nowrap text md value-label">{directoryPath}</span>
          </button>
          <button
            onClick={handleAddSubfolder}
            className={clsx(
              "button icon-button addsubfolder-button pos-rel top-0 right-0",
              { vanished: showSubfolder }
            )}
          >
            <span className="icon addsubfolder-icon icon-size-16"></span>
          </button>
        </div>

        {/* Subfolder */}
        <div
          className={clsx(
            "addsubfolder-container items-center gap-1 flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block",
            { hidden: !showSubfolder }
          )}
        >
          <span className="icon subcat-icon icon-size-16"></span>
          <button
            onClick={onSelectSubfolder}
            className="overflow-hidden flex-1 flex input-with-unit button sm dropdown"
          >
            <span className="text-nowrap value-label text md">{subfolderName}</span>
          </button>
          <button
            onClick={handleRemoveSubfolder}
            className="button icon-button close-button pos-rel top-0 right-0"
          >
            <span className="icon minus-icon icon-size-16"></span>
          </button>
        </div>

        {/* Recording Name */}
        <SubactionHeader text="Recording name" />
        <div className="items-center gap-1 flex flex-row input-string value-selector justify-content-space-between pos-rel inline-block">
          <span className="icon file-icon icon-size-16"></span>
          <button
            onClick={onSelectRecordingName}
            className="overflow-hidden flex-1 flex input-with-unit button sm dropdown"
          >
            {timeStampPrefix && (
              <span className="timestamp-lable text-white text-nowrap text md">
                {formattedTimestamp}
              </span>
            )}
            <span className="text-nowrap value-label text md">{recordingName}</span>
          </button>
        </div>

        {/* Toggles */}
        <ToggleComponent
          text="Timestamp prefix"
          isToggled={timeStampPrefix}
          onToggle={setTimeStampPrefix}
        />
        <ToggleComponent
          text="Auto increment"
          isToggled={autoIncrement}
          onToggle={setAutoIncrement}
        />

        {/* Auto Increment Value */}
        <div
          className={clsx(
            "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
            { disabled: !autoIncrement }
          )}
        >
          <div className="gap-1 text-container overflow-hidden flex items-center">
            <span className="icon icon-size-16 subcat-icon"></span>
            <p className="text text-nowrap text-left md">Number</p>
          </div>
          <ValueSelector
            unit=""
            min={1}
            max={99999}
            initialValue={autoIncrementValue}
            value={autoIncrementValue}
            onChange={setAutoIncrementValue}
          />
        </div>

       {/* close button top-right */}
          <button
            onClick={onClose}
            className="button icon-button close-button pos-abs top-0 right-0 m-1"
          >
            <span className="icon close-icon icon-size-16"></span>
          </button>
      </div>
    </div>
  );
};

export default FileDirectorySettingsModal;
