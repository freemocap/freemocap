export const PROCESSING_STAGES = [
    ['observations', '2D tracking (SkellyTracker)'],
    ['triangulation', 'Triangulation (3D points)'],
    ['filtering', 'Gap filling and filtering'],
    ['scale_fit', 'Person scale fitting'],
    ['reconstruction', 'Skeleton reconstruction and biomechanics'],
] as const;
export type ResumeStage = typeof PROCESSING_STAGES[number][0];
export interface StageSelection {startStage: ResumeStage; stopStage?: ResumeStage; baseRunId: number; sensorGroup?: string;
    runSaveMode?: 'overwrite' | 'new_run';
    pipelineImplementation?: 'current' | 'typed_dataflow';
    graphExecutionProvider?: 'auto' | 'cpu' | 'cuda';
    graphAnnotate?: boolean;
}
