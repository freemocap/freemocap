import {describe, expect, it} from 'vitest';
import {
    getPipelineStageRowTooltip,
    pipelineStagesRowTooltipId,
} from '@/components/pipeline-metrics/pipelineStageTooltips';

const t = (key: string): string => {
    const labels: Record<string, string> = {
        pipelineStages_row_cam_jpeg_encode_msShort: 'JPEG encode',
        pipelineStages_row_cam_jpeg_encode_msLong: 'Server-side JPEG compression for this camera preview frame.',
        pipelineStages_row_unknownShort: 'Timing row',
        pipelineStages_row_unknownLong: 'Duration sample for this pipeline stage.',
    };
    return labels[key] ?? key;
};

describe('pipelineStagesRowTooltipId', () => {
    it('maps camera source keys to cam_* tooltip ids', () => {
        expect(pipelineStagesRowTooltipId('camera:cam0:jpeg_encode_ms')).toBe('cam_jpeg_encode_ms');
    });

    it('maps skeleton inference keys to skel_* tooltip ids', () => {
        expect(pipelineStagesRowTooltipId('skeleton_inference:predict_batch')).toBe('skel_predict_batch');
    });
});

describe('getPipelineStageRowTooltip', () => {
    it('returns localized short and long descriptions', () => {
        expect(getPipelineStageRowTooltip('camera:cam0:jpeg_encode_ms', t)).toEqual({
            short: 'JPEG encode',
            long: 'Server-side JPEG compression for this camera preview frame.',
        });
    });

    it('reuses _ms descriptions for preview keys without the suffix', () => {
        expect(getPipelineStageRowTooltip('camera:cam0:jpeg_encode', t)).toEqual({
            short: 'JPEG encode',
            long: 'Server-side JPEG compression for this camera preview frame.',
        });
    });

    it('falls back to unknown descriptions for unmapped keys', () => {
        expect(getPipelineStageRowTooltip('misc:foo', t)).toEqual({
            short: 'Timing row',
            long: 'Duration sample for this pipeline stage.',
        });
    });
});
