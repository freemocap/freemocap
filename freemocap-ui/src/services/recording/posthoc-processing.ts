export const PROCESSING_STAGES = [
    ['observations', '2D tracking (SkellyTracker)'],
    ['triangulation', 'Triangulation and coordinate alignment'],
    ['filtering', 'Gap filling and filtering'],
    ['scale_fit', 'Person scale fitting'],
    ['reconstruction', 'Skeleton reconstruction and biomechanics'],
] as const;
export type ResumeStage = typeof PROCESSING_STAGES[number][0];
export interface StageSelection {startStage: ResumeStage; baseRunId: number; sensorGroup?: string}
