import {describe, expect, it} from 'vitest';
import {getPipelineStageRowTooltip} from '@/components/pipeline-metrics/pipelineStageTooltips';

const t = (_key: string): string => _key;

describe('getPipelineStageRowTooltip', () => {
    it('returns tooltip for known skeleton_inference stage', () => {
        expect(getPipelineStageRowTooltip('skeleton_inference:predict_batch', t)).toEqual({
            short: 'Batch inference',
            long: 'Total wall-clock time for one batched ONNX inference pass across all cameras.',
        });
    });

    it('returns tooltip for known object_detection stage', () => {
        expect(getPipelineStageRowTooltip('skeleton_inference:object_detection', t)).toEqual({
            short: 'Object detection',
            long: 'Batched human-detection inference that locates people in the camera frames.',
        });
    });

    it('returns tooltip for timer stage', () => {
        expect(getPipelineStageRowTooltip('skeleton_inference:frame_read', t)).toEqual({
            short: 'Frame read',
            long: 'Time to read camera images from the shared memory ring buffer before inference.',
        });
    });

    it('falls back for unknown stage', () => {
        const result = getPipelineStageRowTooltip('unknown:some_stage', t);
        expect(result.short).toBe('some_stage');
        expect(result.long).toBe('No description available for this metric.');
    });
});

    it('falls back to unknown descriptions for unmapped keys', () => {
        expect(getPipelineStageRowTooltip('misc:foo', t)).toEqual({
            short: 'Timing row',
            long: 'Duration sample for this pipeline stage.',
        });
    });
});
