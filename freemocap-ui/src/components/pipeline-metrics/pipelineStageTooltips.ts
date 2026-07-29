import type {TFunction} from 'i18next';

/** Maps internal row keys to i18n suffix pipelineStages_row_<id>{Short,Long}. */
export function pipelineStagesRowTooltipId(rowKey: string): string {
    const parts = rowKey.split(':');
    const head = parts[0];
    if (head === 'aggregator') return `agg_${parts.slice(1).join('_')}`;
    if (head === 'skeleton_inference') return `skel_${parts.slice(1).join('_')}`;
    if (head === 'mediapipe_js') {
        if (parts.length >= 3) {
            return `mpjs_${parts.slice(2).join('_')}`;
        }
        return `mpjs_${parts.slice(1).join('_')}`;
    }
    if (head === 'multiframe') return `mf_${parts.slice(1).join('_')}`;
    if (head === 'camera') return `cam_${parts.slice(2).join('_')}`;
    if (head === 'ui') return `ui_${parts.slice(2).join('_')}`;
    return `misc_${parts.join('_').replace(/:/g, '_')}`;
}

export function getPipelineStageRowTooltip(
    rowKey: string,
    t: TFunction,
): {short: string; long: string} {
    const id = pipelineStagesRowTooltipId(rowKey);
    let shortKey = `pipelineStages_row_${id}Short`;
    let longKey = `pipelineStages_row_${id}Long`;
    let short = t(shortKey);
    let long = t(longKey);
    if ((short === shortKey || long === longKey) && !id.endsWith('_ms')) {
        const idWithMs = `${id}_ms`;
        const shortKeyWithMs = `pipelineStages_row_${idWithMs}Short`;
        const longKeyWithMs = `pipelineStages_row_${idWithMs}Long`;
        const shortWithMs = t(shortKeyWithMs);
        const longWithMs = t(longKeyWithMs);
        if (shortWithMs !== shortKeyWithMs && longWithMs !== longKeyWithMs) {
            shortKey = shortKeyWithMs;
            longKey = longKeyWithMs;
            short = shortWithMs;
            long = longWithMs;
        }
    }
    if (short === shortKey || long === longKey) {
        return {
            short: t('pipelineStages_row_unknownShort'),
            long: t('pipelineStages_row_unknownLong'),
        };
    }
    return {short, long};
}
