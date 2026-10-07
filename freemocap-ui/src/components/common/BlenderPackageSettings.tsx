import React, {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {blenderImportRouteChanged, blenderExportConfigUpdated, blenderPackageChanged, selectBlender, selectEffectiveBlenderExePath, BlenderImportRoute} from '@/store/slices/blender';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

export function BlenderPackageSettings() {
    const dispatch = useAppDispatch();
    const state = useAppSelector(selectBlender);
    const blenderExePath = useAppSelector(selectEffectiveBlenderExePath);
    const canClean = state.importRoute === 'legacy_npy' || state.importRoute === 'parquet_constraints';
    const [archivePath, setArchivePath] = useState('');
    const [message, setMessage] = useState('');
    const [busy, setBusy] = useState(false);
    const [packages, setPackages] = useState<string[]>([]);
    useEffect(() => {setPackages([]); setMessage('');}, [blenderExePath]);
    async function check(install: boolean) {
        setBusy(true);
        setMessage(install ? 'Installing bundled package...' : 'Checking Blender...');
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
                setMessage('Installed and verified. Blender export is ready.');
            } else {
                setPackages(result.packages);
                dispatch(blenderPackageChanged(result.packages.length === 1 ? result.packages[0] : null));
                setMessage(`Blender ${result.blender.join('.')}   Python ${result.python}   ${result.system} ${result.machine}. ` +
                    (result.packages.length ? 'Enabled packages listed below.' : 'Install a matching bundled FreeMoCap ZIP below.'));
            }
        } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
        finally { setBusy(false); }
    }
    return <div className="flex flex-col gap-2 p-1">
        <label className="text sm">Import route
            <select className="input-field" value={state.importRoute} onChange={e => dispatch(blenderImportRouteChanged(e.target.value as BlenderImportRoute))}>
                <option value="auto">Automatic: saved Parquet segments, or legacy NPY</option>
                <option value="parquet_segments">Parquet: saved landmarks and segment poses</option>
                <option value="parquet_constraints">Parquet: landmarks with Blender constraints</option>
                <option value="legacy_npy">Legacy NPY with Blender constraints</option>
            </select>
        </label>
        <fieldset disabled={busy || state.isExporting}>
            <legend>Additional model exports</legend>
            {(['fbx', 'bvh'] as const).map(format => <label key={format}>
                <input type="checkbox" disabled={format === 'bvh' && state.importRoute !== 'legacy_npy'}
                    checked={state.exportConfig.formats.includes(format)} onChange={e => dispatch(blenderExportConfigUpdated({formats: e.target.checked ? [...state.exportConfig.formats, format] : state.exportConfig.formats.filter(f => f !== format)}))} />{format.toUpperCase()}
            </label>)}
            <label>Blender skeleton rest pose
                <select value={state.exportConfig.rest_pose} disabled={!canClean} onChange={e => dispatch(blenderExportConfigUpdated({rest_pose: e.target.value as 'tpose' | 'apose'}))}>
                    <option value="tpose">{canClean ? 'T-pose' : 'Preserve recorded segment poses'}</option><option value="apose">A-pose</option>
                </select>
            </label>
            <label><input type="checkbox" disabled={!canClean} checked={state.exportConfig.apply_foot_locking} onChange={e => dispatch(blenderExportConfigUpdated({apply_foot_locking: e.target.checked}))} />Apply foot locking</label>
            <label><input type="checkbox" disabled={!canClean} checked={state.exportConfig.limit_hand_markers_range_of_motion} onChange={e => dispatch(blenderExportConfigUpdated({limit_hand_markers_range_of_motion: e.target.checked}))} />Limit hand motion</label>
            <p className="text sm">Cleanup edits the Blender animation. Choose a constraint route to enable it. BVH requires legacy NPY. The .blend file is always saved.</p>
        </fieldset>
        <button className="button sm secondary" disabled={!blenderExePath || busy || state.isExporting} onClick={() => void check(false)}>Check Blender package</button>
        <label className="text sm">Enabled FreeMoCap package
            <select className="input-field" value={state.packageName ?? ''} onChange={e => dispatch(blenderPackageChanged(e.target.value || null))}>
                <option value="">Automatically select the only enabled package</option>
                {[...new Set([...packages, ...(state.packageName ? [state.packageName] : [])])].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
        </label>
        <details><summary className="text sm">Install bundled add-on ZIP</summary>
            <p className="text sm">Use a FreeMoCap package built for this Blender version and operating system. Close Blender before installing. Installation updates this Blender version’s saved preferences.</p>
            <input aria-label="Bundled add-on ZIP path" className="input-field" value={archivePath} onChange={e => setArchivePath(e.target.value)} placeholder="Full path to the bundled ZIP" />
            <button className="button sm secondary" disabled={!blenderExePath || !archivePath || busy || state.isExporting} onClick={() => void check(true)}>Install bundled package</button>
        </details>
        {message && <p role="status" className="text sm" style={{whiteSpace: 'pre-wrap'}}>{message}</p>}
    </div>;
}
