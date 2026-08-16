import React from "react";
import {useTranslation} from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { recordingCompletionDismissed } from "@/store/slices/recording/recording-slice";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";
import type {
  RecordingCompletionData,
  StatsSummary,
} from "@/store/slices/recording/recording-types";

function formatStat(value: number, precision: number = 3): string {
  return value.toFixed(precision);
}

interface TimingRow {
  label: string;
  stats: StatsSummary;
}

function TimingStatsTable({ data }: { data: RecordingCompletionData }) {
  const {t} = useTranslation();
  const rows: TimingRow[] = [
    { label: t("completion.framerateMetric"), stats: data.framerate_stats },
    { label: t("completion.frameDurationMetric"), stats: data.frame_duration_stats },
    {
      label: t("completion.cameraSyncMetric"),
      stats: data.inter_camera_grab_range_ms_stats,
    },
  ];

  return (
    <table className="w-full border-collapse">
      <thead>
        <tr>
          <th className=" p-01  text-left border-b-secondary">{t("completion.metric")}</th>
          <th className=" p-01  text-right border-b-secondary">{t("median")}</th>
          <th className=" p-01  text-right border-b-secondary">{t("mean")}</th>
          <th className=" p-01  text-right border-b-secondary">{t("completion.std")}</th>
          <th className=" p-01  text-right border-b-secondary">{t("min")}</th>
          <th className=" p-01  text-right border-b-secondary">{t("max")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <td className="p-01 ">{row.label}</td>
            <td className="p-01  text-right">{formatStat(row.stats.median)}</td>
            <td className="p-01  text-right">{formatStat(row.stats.mean)}</td>
            <td className="p-01  text-right">{formatStat(row.stats.std)}</td>
            <td className="p-01  text-right">{formatStat(row.stats.min)}</td>
            <td className="p-01  text-right">{formatStat(row.stats.max)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export const RecordingCompleteDialog: React.FC = () => {
  const {t} = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { api } = useElectronIPC();
  const completionData = useAppSelector(
    (state) => state.recording.completionData,
  );

  if (!completionData) return null;

  const handleClose = () => dispatch(recordingCompletionDismissed());

  const handleCopyPath = () => {
    navigator.clipboard.writeText(completionData.recording_path);
  };

  const handleOpenFolder = async () => {
    try {
      await api?.fileSystem.openFolder.mutate({
        path: completionData.recording_path,
      });
    } catch (err) {
      console.error("Failed to open recording folder:", err);
    }
  };

  const handleOpenInPlayback = () => {
    dispatch(recordingCompletionDismissed());
    navigate("/playback", {
      state: { loadRecordingPath: completionData.recording_path },
    });
  };

  return (
    <div className="splash-overlay inset-0" onClick={handleClose}>
      <div
        className="recording-completed-main-modal border-1 border-black elevated-sharp pos-rel bg-dark  br-2 flex flex-col p-1 w-full min-w-480 max-w-600"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
            <div className="flex flex-row items-center justify-content-space-between pb-2">
              <p className="text text-white">{t("completion.title")}</p>
              <IconButton icon="close-icon" onClick={handleClose} title={t("close")} tooltip={true} tooltipText={t("completion.closeDialog")} />
            </div>
            <div className="flex flex-row items-center gap-1 mb-2">
              <span className=" text-gray br-1 flex-1 overflow-hidden truncate bg-elevated p-01">
                {completionData.recording_path}
              </span>
              <IconButton
                icon="copy-icon"
                onClick={handleCopyPath}
                title={t("completion.copyPath")}
                tooltip={true}
                tooltipText={t("completion.copyPathHelp")}
              />
              <IconButton
                icon="folder-icon"
                onClick={handleOpenFolder}
                title={t("openFolder")}
                tooltip={true}
                tooltipText={t("completion.openFolderHelp")}
              />
            </div>
            <p className=" text-gray mb-2">
              {t("completion.summary", {
                cameras: completionData.number_of_cameras,
                frames: completionData.number_of_frames,
                seconds: completionData.total_duration_sec,
                fps: completionData.mean_framerate,
              })}
            </p>
            <div className="divider" />
            <p className=" text-white mb-2 font-semibold">
              {t("completion.frameTimingStatistics")}
            </p>
            <TimingStatsTable data={completionData} />
            <div className="flex flex-row gap-4 mt-3 flex-end">
                <ButtonSm
                text={t("close")}
                buttonType="button sm quaternary"
                className=""
                onClick={handleClose}
                tooltip={true}
                tooltipText={t("completion.closeDialog")}
              />
              <ButtonSm
                text={t("completion.openInPlayback")}
                className=""
                iconClass="play-icon"
                buttonType="button sm secondary"
                onClick={handleOpenInPlayback}
                tooltip={true}
                tooltipText={t("completion.openInPlaybackHelp")}
              />
            
            </div>
        </div>
      </div>
    </div>
  );
};
