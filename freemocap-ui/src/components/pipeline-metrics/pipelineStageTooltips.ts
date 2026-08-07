import type {TFunction} from 'i18next';

function _keyFromRowKey(rowKey: string): string {
    return `pipelineMetrics.stages.${rowKey.replace(/:/g, '_')}`;
}

export function getPipelineStageRowTooltip(
    rowKey: string,
    t: TFunction,
): {short: string; long: string} {
    // Try exact match first
    const exactKey = _keyFromRowKey(rowKey);
    const shortLookup = t(`${exactKey}.short`);
    if (shortLookup !== `${exactKey}.short`) {
        return {
            short: shortLookup,
            long: t(`${exactKey}.long`),
        };
    }
    // Normalize nodeKind:cameraId:stage → nodeKind:stage
    const parts = rowKey.split(':');
    if (parts.length >= 3) {
        const normalized = `${parts[0]}:${parts.slice(2).join(':')}`;
        const normalizedKey = _keyFromRowKey(normalized);
        const normShort = t(`${normalizedKey}.short`);
        if (normShort !== `${normalizedKey}.short`) {
            return {
                short: normShort,
                long: t(`${normalizedKey}.long`),
            };
        }
    }
    return {
        short: rowKey.replace(/^.*:/, ''),
        long: t('pipelineMetrics.stages.no_description', 'No description available for this metric.'),
    };
}
