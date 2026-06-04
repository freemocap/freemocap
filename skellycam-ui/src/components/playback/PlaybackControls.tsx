import React, { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import SegmentedControl from "@/components/ui-components/SegmentedControl";
import DesignerCheckbox from "@/components/ui-components/Checkbox";
import type { PlaybackSettings } from "./SyncedVideoPlayer";
import { useTranslation } from "react-i18next";
import IconButton from "@/components/ui-components/IconButton";
import PromptTooltip from "@/components/ui-components/promptTooltip";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import { useDismissibleTooltip } from "@/hooks/useDismissibleTooltip";

interface PlaybackControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  playbackRate: number;
  currentFrame: number;
  totalFrames: number;
  fps: number;
  recordingFps?: number;
  settings: PlaybackSettings;
  onSettingsChange: (settings: PlaybackSettings) => void;
  onPlayPause: () => void;
  onSeekDrag: (frame: number) => void;
  onSeekCommit: (frame: number) => void;
  onFrameStep: (delta: number) => void;
  onPlaybackRateChange: (rate: number) => void;
  onSeekToStart: () => void;
  onSeekToEnd: () => void;
  isLooping: boolean;
  onToggleLoop: () => void;
}

const PLAYBACK_RATES = [0.1, 0.25, 0.5, 1, 1.5, 2, 4, 8];

function formatTimecode(seconds: number, fps: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const frames = Math.floor((seconds % 1) * fps);

  return `${hrs.toString().padStart(2, "0")}:${mins
    .toString()
    .padStart(2, "0")}:${secs.toString().padStart(2, "0")}:${frames
    .toString()
    .padStart(2, "0")}`;
}

function formatTimestamp(
  seconds: number,
  fps: number,
  format: "seconds" | "timecode",
): string {
  if (format === "timecode") {
    return formatTimecode(seconds, fps);
  }

  return `${seconds.toFixed(3)}s`;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  isPlaying,
  currentTime,
  duration,
  playbackRate,
  currentFrame,
  totalFrames,
  fps,
  recordingFps,
  settings,
  onSettingsChange,
  onPlayPause,
  onSeekDrag,
  onSeekCommit,
  onFrameStep,
  onPlaybackRateChange,
  onSeekToStart,
  onSeekToEnd,
  isLooping,
  onToggleLoop,
}) => {
  const { t } = useTranslation();

  // Settings popup
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsButtonRef = useRef<HTMLButtonElement>(null);
  const settingsPopupRef = useRef<HTMLDivElement>(null);
  const [settingsStyle, setSettingsStyle] = useState<React.CSSProperties>({});

  // Speed dropdown
  const [speedDropdownOpen, setSpeedDropdownOpen] = useState(false);
  const speedButtonRef = useRef<HTMLButtonElement>(null);
  const speedPopupRef = useRef<HTMLDivElement>(null);

  // Sync info panel — persists dismissal across reloads
  const [syncInfoOpen, openSyncInfo, dismissSyncInfo] = useDismissibleTooltip(
    "skellycam:tooltip:syncInfo",
  );

  const updateSetting = <K extends keyof PlaybackSettings>(
    key: K,
    value: PlaybackSettings[K],
  ) => {
    onSettingsChange({
      ...settings,
      [key]: value,
    });
  };

  const handleOpenSettings = () => {
    if (!settingsOpen && settingsButtonRef.current) {
      const rect = settingsButtonRef.current.getBoundingClientRect();

      setSettingsStyle({
        position: "fixed",
        bottom: window.innerHeight - rect.top + 4,
        right: window.innerWidth - rect.right,
        zIndex: 200,
      });
    }

    setSettingsOpen((prev) => !prev);
  };

  // Timestamp segmented control options
  const timestampOptions = useMemo(
    () => [
      {
        label: "1.234s",
        value: "seconds",
      },
      {
        label: "HH:MM:SS:FF",
        value: "timecode",
      },
    ],
    [],
  );

  // Close popups on outside click
  useEffect(() => {
    if (!settingsOpen && !speedDropdownOpen) return;

    const handleClick = (e: MouseEvent) => {
      if (
        settingsPopupRef.current &&
        !settingsPopupRef.current.contains(e.target as Node) &&
        settingsButtonRef.current &&
        !settingsButtonRef.current.contains(e.target as Node)
      ) {
        setSettingsOpen(false);
      }
      if (
        speedPopupRef.current &&
        !speedPopupRef.current.contains(e.target as Node) &&
        speedButtonRef.current &&
        !speedButtonRef.current.contains(e.target as Node)
      ) {
        setSpeedDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClick);

    return () => document.removeEventListener("mousedown", handleClick);
  }, [settingsOpen, speedDropdownOpen]);

  return (
    <div className="playback-controls bg-dark br-2 flex flex-row flex-wrap row-reverse justify-center gap-2 p-2">
      {/* Timeline Scrubber */}
      {/* Timeline Scrubber */}
<div className="playback-timeline-scrubber flex flex-row items-center">
  <div className="playback-timeline-track flex-1 bg-middark relative">
    <input
      type="range"
      dir="ltr"
      className="playback-timeline-input"
      min={0}
      max={Math.max(totalFrames - 1, 1)}
      step={1}
      value={currentFrame}
      style={
        {
          "--progress-percent": `${
            totalFrames > 1
              ? (currentFrame / (totalFrames - 1)) * 100
              : 0
          }%`,
        } as React.CSSProperties
      }
      onChange={(e) => onSeekDrag(Number(e.target.value))}
      onMouseUp={(e) => onSeekCommit(Number(e.currentTarget.value))}
      onTouchEnd={(e) => onSeekCommit(Number(e.currentTarget.value))}
    />

    <div className="playback-timeline-frame-counter pos-abs z-2 text-white gap-3 flex flex-row items-center">
      Frame {currentFrame} / {totalFrames}

      {recordingFps != null && recordingFps > 0 && (
        <span title={t("recordingCaptureFps")}>
          · Rec: {recordingFps} fps
        </span>
      )}
    </div>

    <span
      className="playback-timeline-start-time pos-abs z-2 text-white"
      title={t("estimatedTime")}
    >
      {formatTimestamp(currentTime, fps, settings.timestampFormat)}
    </span>

    <span
      className="playback-timeline-end-time pos-abs z-2 text-white"
      title={t("estimatedDuration")}
    >
      {formatTimestamp(duration, fps, settings.timestampFormat)}
    </span>
  </div>
</div>

      {/* Transport Controls Row */}
      <div className="flex items-center justify-center controls-group-section gap-2 flex-wrap">
        {/* Loop & Speed Group */}
        <div className="playback-controls-group-loop-speed flex bg-middark br-2 flex-row p-1 gap-1">
          <IconButton
            icon={isLooping ? "loopactive-icon" : "loop-icon"}
            onClick={onToggleLoop}
            title={isLooping ? t("loopOn") : t("loopOff")}
            className={clsx("icon-size-28", isLooping && "activated")}
            tooltip={true}
            tooltipText={isLooping ? t("loopOn") : t("loopOff")}
            tooltipPosition="pos-top"
          />

          <div className="playback-speed-button-containter pos-rel">
            <button
              ref={speedButtonRef}
              className="playback-speed-button icon-size-28 button sm fit-content flex-inline items-center gap-1 br-1"
              onClick={() => setSpeedDropdownOpen((prev) => !prev)}
              title={t("playbackSpeed")}
            >
              <span className="text-gray text md text-nowrap">
                {playbackRate}×
              </span>
            </button>

            {speedDropdownOpen && (
              <div
                ref={speedPopupRef}
                className="reveal slide-up right-0 z-10 pos-abs bottom-36 playback-speed-settings-popup border-1 border-solid bg-dark border-black br-2 elevated-sharp flex flex-col gap-2 p-1"
              >
                <div className="bg-middark br-1 flex flex-col gap-1 p-1">
                  {PLAYBACK_RATES.map((rate) => (
                    <button
                      key={rate}
                      className={`gap-1 br-1 button sm fit-content flex-inline text-left items-center full-width ${
                        playbackRate === rate ? "selected" : ""
                      }`}
                      onClick={() => {
                        onPlaybackRateChange(rate);
                        setSpeedDropdownOpen(false);
                      }}
                    >
                      <p className="text-gray text md text-align-left text-nowrap">
                        {rate}×
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Step & Skip Group */}
        <div className="playback-controls-group-step-skip bg-middark br-2 gap-1 flex flex-row p-1 items-center">
          <IconButton
            icon="skipbackward-icon"
            onClick={onSeekToStart}
            title={t("jumpToStart")}
            className="icon-size-28"
            tooltip={true}
            tooltipText={t("jumpToStart")}
            tooltipPosition="pos-top"
          />

          <IconButton
            icon="framebackward-icon"
            onClick={() => onFrameStep(-1)}
            title={t("previousFrame")}
            className="icon-size-28"
            tooltip={true}
            tooltipText={t("previousFrame")}
            tooltipPosition="pos-top"
          />

          <IconButton
            icon={isPlaying ? "pause-icon" : "play-icon"}
            onClick={onPlayPause}
            title={isPlaying ? "Pause (Space)" : "Play (Space)"}
            className={clsx(
              "playback-btn-play",
              "icon-size-28",
              isPlaying && "playing",
            )}
            tooltip={true}
            tooltipText={isPlaying ? t("pause") : t("play")}
            tooltipPosition="pos-top"
          />

          <IconButton
            icon="frameforward-icon"
            onClick={() => onFrameStep(1)}
            title={t("nextFrame")}
            className="icon-size-28"
            tooltip={true}
            tooltipText={t("nextFrame")}
            tooltipPosition="pos-top"
          />

          <IconButton
            icon="skipforward-icon"
            onClick={onSeekToEnd}
            title={t("jumpToEnd")}
            className="icon-size-28"
            tooltip={true}
            tooltipText={t("jumpToEnd")}
            tooltipPosition="pos-top"
          />
        </div>

        {/* Info & Settings Group */}
        <div className="playback-controls-group-info-settings flex items-center gap-1 flow-row p-1 bg-middark br-2">
          <div className="flex pos-rel items-center onclick-tooltip-wrapper">
            <PromptTooltip
              show={syncInfoOpen}
              title="Recording Playback Timing Issue"
              text={t("syncInfoTitle")}
              position="pos-top"
              variant="warning"
              onClose={dismissSyncInfo}
            />

            <IconButton
              icon="warning-icon"
              onClick={() => (syncInfoOpen ? dismissSyncInfo() : openSyncInfo())}
              title={t("syncInfo")}
              className={clsx("icon-size-28", syncInfoOpen && "activated")}
              tooltip={true}
              tooltipText={t("syncInfo")}
              tooltipPosition="pos-top"
            />
          </div>

          <div className="playback-settings-button-opener flex pos-rel items-center onclick-tooltip-wrapper">
            <IconButton
              icon="settings-icon"
              ref={settingsButtonRef}
              onClick={handleOpenSettings}
              title={t("playbackSettings")}
              className={clsx("icon-size-28", settingsOpen && "activated")}
              tooltip={true}
              tooltipText={t("playbackSettings")}
              tooltipPosition="pos-top"
            />
            {/* Settings popup */}
            {settingsOpen && (
              <div
                ref={settingsPopupRef}
                className="reveal slide-up right-0 z-10 pos-abs bottom-36 playback-settings-popup border-1 border-solid  bg-dark border-black br-2 elevated-sharp flex flex-col gap-2 p-1"
              >
                <div className="bg-middark br-1 flex flex-col gap-2 p-2">
                  <SubactionHeader text="Display settings" />
                  <ToggleComponent
                    text="Show frame overlays"
                    isToggled={settings.showOverlays}
                    onToggle={(state) => updateSetting("showOverlays", state)}
                  />
                  <div className="timestamp-format-section  flex flex-col gap-2 p-1">
                    <div className="flex items-center justify-between">
                      <p className="text sm text-gray">Timestamp format</p>
                      {/* <span className="text sm text-white">
                      {formatTimestamp(currentTime, fps, settings.timestampFormat)}
                    </span> */}
                    </div>
                    <SegmentedControl
                      options={timestampOptions}
                      value={settings.timestampFormat}
                      onChange={(val) =>
                        updateSetting(
                          "timestampFormat",
                          val as "seconds" | "timecode",
                        )
                      }
                      size="sm"
                      className="bg-darkgray segmented-control-sm gap-2"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
