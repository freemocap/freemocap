import React from 'react';
import { Box, Typography } from '@mui/material';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { FullRecordingPathPreview } from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import { RecordingControlsSection } from "@/components/recording-info-panel/RecordingControlsTreeSection";

interface RecordingPathTreeItemProps {
  recordingDirectory: string;
  recordingName: string;
  subfolder?: string;
  countdown: number | null;
  // Add all the control props
  recordingTag: string;
  useDelayStart: boolean;
  delaySeconds: number;
  useTimestamp: boolean;
  baseName: string;
  useIncrement: boolean;
  currentIncrement: number;
  createSubfolder: boolean;
  customSubfolderName: string;
  isRecording: boolean;
  onDelayToggle: (value: boolean) => void;
  onDelayChange: (value: number) => void;
  onTagChange: (value: string) => void;
  onUseTimestampChange: (value: boolean) => void;
  onBaseNameChange: (value: string) => void;
  onUseIncrementChange: (value: boolean) => void;
  onIncrementChange: (value: number) => void;
  onCreateSubfolderChange: (value: boolean) => void;
  onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathTreeItem: React.FC<RecordingPathTreeItemProps> = ({
  recordingDirectory,
  recordingName,
  subfolder,
  countdown,
  // Control props
  recordingTag,
  useDelayStart,
  delaySeconds,
  useTimestamp,
  baseName,
  useIncrement,
  currentIncrement,
  createSubfolder,
  customSubfolderName,
  isRecording,
  onDelayToggle,
  onDelayChange,
  onTagChange,
  onUseTimestampChange,
  onBaseNameChange,
  onUseIncrementChange,
  onIncrementChange,
  onCreateSubfolderChange,
  onCustomSubfolderNameChange
}) => {
  return (
    <TreeItem
      itemId="recording-path"
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FullRecordingPathPreview
            directory={recordingDirectory}
            filename={recordingName}
            subfolder={subfolder}
          />
        </Box>
      }
    >
      <Box sx={{ pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Countdown display in controls section */}
        {countdown !== null && (
          <Typography variant="h4" align="center" color="secondary">
            Starting in {countdown}...
          </Typography>
        )}

        <RecordingControlsSection
          recordingDirectory={recordingDirectory}
          recordingName={recordingName}
          recordingTag={recordingTag}
          useDelayStart={useDelayStart}
          delaySeconds={delaySeconds}
          useTimestamp={useTimestamp}
          baseName={baseName}
          useIncrement={useIncrement}
          currentIncrement={currentIncrement}
          createSubfolder={createSubfolder}
          customSubfolderName={customSubfolderName}
          isRecording={isRecording}
          onDelayToggle={onDelayToggle}
          onDelayChange={onDelayChange}
          onTagChange={onTagChange}
          onUseTimestampChange={onUseTimestampChange}
          onBaseNameChange={onBaseNameChange}
          onUseIncrementChange={onUseIncrementChange}
          onIncrementChange={onIncrementChange}
          onCreateSubfolderChange={onCreateSubfolderChange}
          onCustomSubfolderNameChange={onCustomSubfolderNameChange}
        />
      </Box>
    </TreeItem>
  );
};