import {useState} from 'react';
import {BlenderPackageSettings} from '@/components/common/BlenderPackageSettings';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import DependentRowGroup from '@/components/common/settings-layout/dependent-row-group';
import {useMocap} from '@/hooks/useMocap';
import {useBlender} from '@/hooks/useBlender';
import {useElectronIPC} from '@/services';

const EXECUTABLE_GROUP_INFO = {
    title: 'Blender',
    text: <>
        <p>The Blender installation FreeMoCap drives to build a .blend file from the processed recording.</p>
        <p><em>Autodetect searches the usual install locations. Choose the executable yourself to use a specific version.</em></p>
    </>,
};

const EXECUTABLE_INFO = {
    title: 'Blender executable',
    text: <p>Click the path to choose a different blender executable. A chosen path takes priority over the auto-detected one.</p>,
};

const LOCATE_INFO = {
    title: 'Locate Blender',
    text: <p><strong>Autodetect</strong> searches again for an installed Blender. <strong>Use detected</strong> drops a manually chosen path.</p>,
};

const EXPORT_AFTER_INFO = {
    title: 'Export after mocap processing',
    text: <p>Builds the .blend file automatically when mocap processing completes.</p>,
};

const AUTO_OPEN_INFO = {
    title: 'Open when done',
    text: <p>Launches Blender with the new .blend file after the automatic export finishes.</p>,
};

const RUN_GROUP_INFO = {
    title: 'Run now',
    text: <p>Export or open the active recording immediately with the settings above, without reprocessing mocap.</p>,
};

const EXPORT_NOW_INFO = {
    title: 'Export to Blender',
    text: <p>Builds the .blend file for the active recording from its saved processing results.</p>,
};

const OPEN_NOW_INFO = {
    title: 'Open in Blender',
    text: <p>Launches Blender and opens the active recording’s .blend file.</p>,
};

export default function MocapBlenderSettings() {
    const {mocapRecordingPath} = useMocap();
    const {api, isElectron} = useElectronIPC();
    const [selectError, setSelectError] = useState('');
    const {
        effectiveBlenderExePath,
        isUsingManualBlenderPath,
        exportToBlenderEnabled,
        autoOpenBlendFile,
        isExporting,
        isDetecting,
        isOpening,
        lastBlendFilePath,
        error,
        redetectBlender,
        setBlenderExePath,
        clearBlenderExePath,
        setExportToBlenderEnabled,
        setAutoOpenBlendFile,
        triggerBlenderExport,
        triggerOpenInBlender,
        clearError,
    } = useBlender();

    const selectBlenderExe = async (): Promise<void> => {
        if (!isElectron || !api) throw new Error('Choosing the Blender executable requires the desktop app');
        setSelectError('');
        try {
            const result: string | null = await api.fileSystem.selectExecutableFile.mutate();
            if (result) setBlenderExePath(result);
        } catch (reason) {
            setSelectError(reason instanceof Error ? reason.message : String(reason));
        }
    };

    const canExport = !!mocapRecordingPath && !!effectiveBlenderExePath && !isExporting;
    const canOpen = !!mocapRecordingPath && !!effectiveBlenderExePath && !isOpening;

    return <>
        <SettingsGroupHeading text="Blender" info={EXECUTABLE_GROUP_INFO}/>
        <SettingRow label={<>Blender executable <SettingsSummaryChip tone="quiet">
            {isUsingManualBlenderPath ? 'manual' : effectiveBlenderExePath ? 'auto-detected' : ''}
        </SettingsSummaryChip></>} info={EXECUTABLE_INFO}
            control={<button type="button" className="setting-path-button" disabled={!isElectron}
                title={effectiveBlenderExePath ?? 'Choose the Blender executable'}
                onClick={() => void selectBlenderExe()}>
                {effectiveBlenderExePath
                    ? <bdi dir="ltr">{effectiveBlenderExePath}</bdi>
                    : <span className="setting-path-placeholder">{isDetecting ? 'Detecting…' : 'Choose blender executable'}</span>}
            </button>}/>
        <SettingRow label="Locate Blender" info={LOCATE_INFO}
            control={<>
                {isUsingManualBlenderPath && <ButtonSm text="Use detected" className="setting-action-button"
                    textColor="text-white" onClick={clearBlenderExePath}/>}
                <ButtonSm text={isDetecting ? 'Detecting…' : 'Autodetect'} className="setting-action-button"
                    textColor="text-white" disabled={isDetecting} onClick={redetectBlender}/>
            </>}/>
        {selectError && <p role="alert" className="settings-note settings-note-error">{selectError}</p>}

        <SettingRow label="Export after mocap processing" info={EXPORT_AFTER_INFO}
            control={<SettingToggleSwitch label="Export to Blender after mocap processing"
                isToggled={exportToBlenderEnabled} onToggle={setExportToBlenderEnabled}/>}/>
        <DependentRowGroup>
            <SettingRow label="Open .blend when done" info={AUTO_OPEN_INFO} inactive={!exportToBlenderEnabled}
                control={<SettingToggleSwitch label="Open .blend file in Blender when done"
                    isToggled={autoOpenBlendFile} disabled={!exportToBlenderEnabled}
                    onToggle={setAutoOpenBlendFile}/>}/>
        </DependentRowGroup>

        <BlenderPackageSettings/>

        <SettingsGroupHeading text="Run now" info={RUN_GROUP_INFO}/>
        <SettingRow label="Export to Blender" info={EXPORT_NOW_INFO} inactive={!canExport && !isExporting}
            control={<ButtonSm text={isExporting ? 'Exporting…' : 'Export recording'} className="setting-action-button"
                textColor="text-white" disabled={!canExport}
                onClick={() => {if (mocapRecordingPath) void triggerBlenderExport(mocapRecordingPath);}}/>}/>
        <SettingRow label="Open in Blender" info={OPEN_NOW_INFO} inactive={!canOpen && !isOpening}
            control={<ButtonSm text={isOpening ? 'Opening…' : 'Open .blend'} className="setting-action-button"
                textColor="text-white" disabled={!canOpen}
                onClick={() => {if (mocapRecordingPath) void triggerOpenInBlender(mocapRecordingPath);}}/>}/>
        {lastBlendFilePath && <p className="settings-note">
            Last export: <SettingsSummaryChip tone="path" title={lastBlendFilePath}>{lastBlendFilePath}</SettingsSummaryChip>
        </p>}
        {error && <div role="alert" className="settings-note settings-note-error settings-note-dismissable">
            <span>{error}</span>
            <ButtonSm text="Dismiss" className="setting-action-button" textColor="text-white" onClick={clearError}/>
        </div>}
    </>;
}
