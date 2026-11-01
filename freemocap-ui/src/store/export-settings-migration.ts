/** Historical local settings are input aliases, never names written by new clients. */
const aliases = {
    scientificExportFormats: 'exportFormats',
    scientificExportData: 'exportChannels',
    scientificExportChannels: 'exportChannelOverrides',
    scientificExportAfterProcessing: 'exportAfterProcessing',
} as const;

function signature(value: unknown): string {
    if (Array.isArray(value)) return `[${value.map(signature).join(',')}]`;
    if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => `${JSON.stringify(key)}:${signature(item)}`).join(',')}}`;
    return JSON.stringify(value) ?? 'undefined';
}

export function migrateExportSettings(saved: Record<string, unknown> | null): {
    config: Record<string, unknown>; error: string | null;
} {
    const config = {...saved};
    const conflicts: string[] = [];
    for (const [oldName, name] of Object.entries(aliases)) {
        if (!(oldName in config)) continue;
        if (name in config && signature(config[name]) !== signature(config[oldName])) conflicts.push(name);
        else config[name] = config[oldName];
        delete config[oldName];
    }
    if (!conflicts.length) return {config, error: null};
    // Do not choose one conflicting value or overwrite saved settings. Hydrate
    // safe defaults until the user explicitly resets the export settings.
    for (const name of Object.values(aliases)) delete config[name];
    return {config, error: `Saved export settings conflict (${conflicts.join(', ')}). Reset export settings to continue.`};
}
