import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    blenderExportConfigUpdated,
    blenderImportRouteChanged,
    blenderPackageChanged,
    type BlenderImportRoute,
    selectBlender,
    selectEffectiveBlenderExePath,
} from '@/store/slices/blender';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';

const IMPORT_ROUTES: {value: BlenderImportRoute; label: string}[] = [
    {value: 'auto', label: 'Automatic'},
    {value: 'parquet_segments', label: 'Parquet segment poses'},
    {value: 'parquet_constraints', label: 'Parquet + constraints'},
    {value: 'legacy_npy', label: 'Legacy NPY + constraints'},
];

const AUTOMATIC_PACKAGE = '';

const IMPORT_GROUP_INFO = {
    title: 'Blender import',
    text: <>
        <p>How the processed recording is brought into Blender, and what cleanup Blender applies to the animation.</p>
        <p><em>The .blend file is always saved.</em></p>
    </>,
};

const ROUTE_INFO = {
    title: 'Import route',
    text: <>
        <p><strong>Automatic</strong> uses saved Parquet segments when present, otherwise legacy NPY.</p>
        <p><strong>Parquet segment poses</strong> imports saved landmarks and segment poses as recorded.</p>
        <p><strong>Parquet + constraints</strong> imports landmarks and drives the rig with Blender constraints.</p>
        <p><strong>Legacy NPY + constraints</strong> uses the legacy NPY data with Blender constraints. Required for BVH.</p>
        <p><em>Rest pose, foot locking and hand limits need a constraint route.</em></p>
    </>,
};

const REST_POSE_INFO = {
    title: 'Rest pose',
    text: <p>The rest pose of the Blender skeleton. Segment-pose routes preserve the recorded segment poses, so this needs a constraint route.</p>,
};

const FOOT_LOCKING_INFO = {
    title: 'Foot locking',
    text: <p>Pins feet to the floor during ground contact to remove sliding. Edits the Blender animation; needs a constraint route.</p>,
};

const HAND_LIMIT_INFO = {
    title: 'Limit hand motion',
    text: <p>Restricts hand markers to an anatomical range of motion. Edits the Blender animation; needs a constraint route.</p>,
};

const MODEL_EXPORTS_INFO = {
    title: 'Additional model exports',
    text: <>
        <p>Model files written next to the .blend file.</p>
        <p><em>BVH needs the Legacy NPY import route.</em></p>
    </>,
};

const ADDON_GROUP_INFO = {
    title: 'FreeMoCap add-on',
    text: <>
        <p>Blender export runs through the FreeMoCap add-on enabled in the selected Blender.</p>
        <p>Check the package to list enabled add-ons. Install a bundled ZIP built for this Blender version and operating system if none is enabled.</p>
    </>,
};

const PACKAGE_INFO = {
    title: 'Add-on package',
    text: <p>The enabled FreeMoCap package used for export. Automatic selects the only enabled package and fails if there is more than one.</p>,
};

const CHECK_INFO = {
    title: 'Check Blender',
    text: <p>Inspects the selected Blender: version, Python, platform and enabled FreeMoCap packages.</p>,
};

const INSTALL_INFO = {
    title: 'Install bundled add-on',
    text: <>
        <p>Full path to a FreeMoCap package ZIP built for this Blender version and operating system.</p>
        <p><em>Close Blender before installing. Installation updates this Blender version’s saved preferences.</em></p>
    </>,
};

type Notice = {kind: 'status' | 'error'; text: string};

/**
 * Blender import, model export and add-on package settings, rendered as setting rows.
 * Renders inside a settings section, or inside a `.settings-layout-stacked` container
 * where the panel is too narrow for the control column.
 */
export function BlenderPackageSettings() {
    const dispatch = useAppDispatch();
    const state = useAppSelector(selectBlender);
    const blenderExePath = useAppSelector(selectEffectiveBlenderExePath);
    const [archivePath, setArchivePath] = useState('');
    const [notice, setNotice] = useState<Notice | null>(null);
    const [busy, setBusy] = useState(false);
    const [packages, setPackages] = useState<string[]>([]);

    useEffect(() => {
        setPackages([]);
        setNotice(null);
    }, [blenderExePath]);

    const canClean = state.importRoute === 'legacy_npy' || state.importRoute === 'parquet_constraints';
    const locked = busy || state.isExporting;
    const formats = state.exportConfig.formats;
    const setFormat = (format: 'fbx' | 'bvh', enabled: boolean): void => {
        dispatch(blenderExportConfigUpdated({
            formats: enabled ? [...formats, format] : formats.filter(item => item !== format),
        }));
    };

    async function inspect(install: boolean): Promise<void> {
        setBusy(true);
        setNotice({kind: 'status', text: install ? 'Installing bundled package…' : 'Checking Blender…'});
        try {
            const base = serverUrls.endpoints.blenderExport.replace(/\/export$/, '');
            const response = await fetch(base + (install ? '/addon/install' : '/inspect'), {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({blenderExePath, ...(install ? {archivePath} : {})}),
            });
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const result = await response.json();
            if (install) {
                dispatch(blenderPackageChanged(result.package));
                setPackages([result.package]);
                setNotice({kind: 'status', text: 'Installed and verified. Blender export is ready.'});
            } else {
                setPackages(result.packages);
                dispatch(blenderPackageChanged(result.packages.length === 1 ? result.packages[0] : null));
                setNotice({
                    kind: result.packages.length ? 'status' : 'error',
                    text: `Blender ${result.blender.join('.')} · Python ${result.python} · ${result.system} ${result.machine}. `
                        + (result.packages.length
                            ? `${result.packages.length} enabled FreeMoCap package${result.packages.length === 1 ? '' : 's'}.`
                            : 'No FreeMoCap package enabled. Install a bundled ZIP below.'),
                });
            }
        } catch (error) {
            setNotice({kind: 'error', text: error instanceof Error ? error.message : String(error)});
        } finally {
            setBusy(false);
        }
    }

    const packageOptions = [
        {value: AUTOMATIC_PACKAGE, label: 'Automatic'},
        ...[...new Set([...packages, ...(state.packageName ? [state.packageName] : [])])]
            .map(name => ({value: name, label: name})),
    ];

    return <>
        <SettingsGroupHeading text="Blender import" info={IMPORT_GROUP_INFO}/>
        <SettingRow label="Import route" info={ROUTE_INFO}
            control={<SettingSelectInput label="Import route" value={state.importRoute} options={IMPORT_ROUTES}
                disabled={locked} onChange={route => dispatch(blenderImportRouteChanged(route))}/>}/>
        <SettingRow label="Rest pose" info={REST_POSE_INFO} inactive={!canClean}
            control={<SettingSelectInput label="Rest pose" value={state.exportConfig.rest_pose}
                options={canClean
                    ? [{value: 'tpose', label: 'T-pose'}, {value: 'apose', label: 'A-pose'}]
                    : [{value: 'tpose', label: 'Recorded segment poses'}]}
                disabled={locked || !canClean}
                onChange={restPose => dispatch(blenderExportConfigUpdated({rest_pose: restPose}))}/>}/>
        <SettingRow label="Foot locking" info={FOOT_LOCKING_INFO} inactive={!canClean}
            control={<SettingToggleSwitch label="Foot locking" isToggled={state.exportConfig.apply_foot_locking}
                disabled={locked || !canClean}
                onToggle={enabled => dispatch(blenderExportConfigUpdated({apply_foot_locking: enabled}))}/>}/>
        <SettingRow label="Limit hand motion" info={HAND_LIMIT_INFO} inactive={!canClean}
            control={<SettingToggleSwitch label="Limit hand motion"
                isToggled={state.exportConfig.limit_hand_markers_range_of_motion} disabled={locked || !canClean}
                onToggle={enabled => dispatch(blenderExportConfigUpdated({limit_hand_markers_range_of_motion: enabled}))}/>}/>

        <SettingsGroupHeading text="Additional model exports" info={MODEL_EXPORTS_INFO}/>
        <SettingRow label="FBX" info={MODEL_EXPORTS_INFO}
            control={<SettingToggleSwitch label="Export FBX" isToggled={formats.includes('fbx')} disabled={locked}
                onToggle={enabled => setFormat('fbx', enabled)}/>}/>
        <SettingRow label="BVH" info={MODEL_EXPORTS_INFO} inactive={state.importRoute !== 'legacy_npy'}
            control={<SettingToggleSwitch label="Export BVH" isToggled={formats.includes('bvh')}
                disabled={locked || state.importRoute !== 'legacy_npy'}
                onToggle={enabled => setFormat('bvh', enabled)}/>}/>

        <SettingsGroupHeading text="FreeMoCap add-on" info={ADDON_GROUP_INFO}/>
        <SettingRow label="Add-on package" info={PACKAGE_INFO}
            control={<SettingSelectInput label="Add-on package" value={state.packageName ?? AUTOMATIC_PACKAGE}
                options={packageOptions} disabled={locked}
                onChange={name => dispatch(blenderPackageChanged(name === AUTOMATIC_PACKAGE ? null : name))}/>}/>
        <SettingRow label="Check Blender" info={CHECK_INFO} inactive={!blenderExePath}
            control={<ButtonSm text={busy ? 'Working…' : 'Check package'} className="setting-action-button"
                textColor="text-white" disabled={!blenderExePath || locked} onClick={() => void inspect(false)}/>}/>
        <SettingRow label="Bundled add-on ZIP" info={INSTALL_INFO}
            control={<input aria-label="Bundled add-on ZIP path" className="setting-text-input" value={archivePath}
                placeholder="Full path to ZIP" disabled={locked} onChange={event => setArchivePath(event.target.value)}/>}/>
        <SettingRow label="Install add-on" info={INSTALL_INFO} inactive={!blenderExePath || !archivePath}
            control={<ButtonSm text="Install bundled package" className="setting-action-button" textColor="text-white"
                disabled={!blenderExePath || !archivePath || locked} onClick={() => void inspect(true)}/>}/>
        {notice && <p role={notice.kind === 'error' ? 'alert' : 'status'}
            className={`settings-note${notice.kind === 'error' ? ' settings-note-error' : ''}`}>{notice.text}</p>}
    </>;
}
