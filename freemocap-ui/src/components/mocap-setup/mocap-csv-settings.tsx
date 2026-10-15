import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {exportTallCsvUpdated} from '@/store/slices/mocap';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';

const CSV_INFO = {
    title: 'Tall CSV',
    text: <>
        <p>Save one measurement per row, preserving recorded values, timestamps, names and units.</p>
        <p>Files go into the recording’s exports folder, alongside metadata and a separate table of fixed measurements. Existing default CSV exports are replaced.</p>
    </>,
};
const AUTOMATIC_INFO = {
    title: 'Save tall CSV after processing',
    text: <p>Export the completed result automatically after full processing or saved-stage reprocessing. Turn this off to save CSV only when requested.</p>,
};
const SAVED_INFO = {
    title: 'Export saved result',
    text: <p>Choose a saved run and export all its measurements without rerunning processing. Large recordings may take several minutes.</p>,
};

interface Selection {run_ids: number[]; selected_run_id: number; revision: string}

export default function MocapCsvSettings({path, processing, sourceRunId}: {path: string | null; processing: boolean; sourceRunId: number}) {
    const dispatch = useAppDispatch();
    const enabled = useAppSelector(state => state.mocap.config.exportTallCsv ?? false);
    const [selection, setSelection] = useState<Selection | null>(null);
    const run = sourceRunId;
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [noSavedResult, setNoSavedResult] = useState(false);
    const [saved, setSaved] = useState<string[]>([]);
    const [refresh, setRefresh] = useState(0);
    const endpoint = `${serverUrls.getHttpUrl()}/freemocap/exports/tall-csv`;

    useEffect(() => {
        const controller = new AbortController();
        setNoSavedResult(false);
        setSelection(null); setError(''); setSaved([]);
        if (!path || processing) return () => controller.abort();
        void (async () => {
            try {
                const response = await fetch(`${endpoint}?recording_path=${encodeURIComponent(path)}`, {signal: controller.signal});
                if (response.status === 204) {
                    if (!controller.signal.aborted) setNoSavedResult(true);
                    return;
                }
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const data: Selection = await response.json();
                if (!controller.signal.aborted) {setSelection(data);}
            } catch (reason) {
                if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
            }
        })();
        return () => controller.abort();
    }, [path, processing, refresh, endpoint]);

    async function save() {
        if (!selection || !path || busy) return;
        setBusy(true); setError(''); setSaved([]);
        try {
            const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({recording_path: path, run_id: run, expected_revision: selection.revision})});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const result: {files: string[]; manifest_path: string} = await response.json();
            setSaved([...result.files, result.manifest_path]);
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
        finally {setBusy(false);}
    }

    return <>
        <SettingsGroupHeading text="Tall CSV" info={CSV_INFO}/>
        <SettingRow label="Save after processing" info={AUTOMATIC_INFO}
            control={<SettingToggleSwitch label="Save tall CSV after processing" isToggled={enabled}
                onToggle={value => dispatch(exportTallCsvUpdated(value))}/>}/>
        <p className="settings-note">Export saved Run {run}, selected under Processing stages.</p>
        <SettingRow label="Export saved result" info={SAVED_INFO}
            inactive={!selection || processing}
            control={<ButtonSm text={busy ? 'Saving…' : 'Export now'} onClick={() => void save()}
                disabled={!selection || busy || processing} className="setting-action-button" textColor="text-white"/>}/>
        {busy && <p role="status" className="settings-note">Saving CSV files…</p>}
        {noSavedResult && <p role="status" className="settings-note">No saved result yet. Process the recording to export saved data.</p>}
        {error && <div role="alert" className="settings-note settings-note-error settings-note-dismissable">
            <span>{error}</span>
            <ButtonSm text="Reload saved results" className="setting-action-button" textColor="text-white"
                disabled={busy || processing} onClick={() => setRefresh(value => value + 1)}/>
        </div>}
        {saved.length > 0 && <div role="status" className="settings-note settings-note-list">
            <span>Tall CSV saved:</span>
            {saved.map(file => <SettingsSummaryChip key={file} tone="path" title={file}>{file}</SettingsSummaryChip>)}
        </div>}
    </>;
}
