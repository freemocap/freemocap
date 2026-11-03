import type {ResumeStage} from '@/services/recording/posthoc-processing';

/** The processing stages' names everywhere in the Mocap processing window. */
export const STAGE_TITLES: Record<ResumeStage, string> = {
    observations: '2D tracking', triangulation: 'Triangulation', filtering: 'Gap filling and filtering',
    scale_fit: 'Person scale fitting', reconstruction: 'Skeleton reconstruction',
};
