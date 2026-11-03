import {useEffect, useState} from 'react';
import {useAppSelector} from '@/store/hooks';
import {mocapProcessingConfig} from '@/store/slices/mocap/mocap-thunks';
import type {StageSelection} from '@/services/recording/posthoc-processing';
import {previewProcessingPlan, type PlanPreview} from '@/services/recording/processing-plan';

export interface ProcessingPlanState {
    preview: PlanPreview | null;
    loading: boolean;
    failure: string;
}

/** Waiting this long after the last settings change avoids a request per keystroke. */
const PREVIEW_DELAY_MS = 250;

/**
 * The plan the server would run for the current settings and stage selection.
 * The configuration is the one Process sends, so the preview and the run match.
 */
export function useProcessingPlan(path: string | null, selection: StageSelection | null): ProcessingPlanState {
    const configJson = useAppSelector(state => selection ? JSON.stringify(mocapProcessingConfig(state, selection)) : null);
    const [result, setResult] = useState<ProcessingPlanState>({preview: null, loading: false, failure: ''});

    useEffect(() => {
        if (!path || !configJson) {
            setResult({preview: null, loading: false, failure: ''});
            return;
        }
        const controller = new AbortController();
        setResult(previous => ({...previous, loading: true}));
        const timer = window.setTimeout(() => {
            previewProcessingPlan(path, JSON.parse(configJson) as Record<string, unknown>, controller.signal)
                .then(preview => setResult({preview, loading: false, failure: ''}))
                .catch((reason: unknown) => {
                    if (controller.signal.aborted) return;
                    setResult({preview: null, loading: false, failure: reason instanceof Error ? reason.message : String(reason)});
                });
        }, PREVIEW_DELAY_MS);
        return () => {
            controller.abort();
            window.clearTimeout(timer);
        };
    }, [path, configJson]);

    return result;
}
