export enum MatchingFailurePolicy {
    Continue = 'continue',
    Stop = 'stop',
}

export interface CameraMatchingOptions {
    automatically_match: boolean;
    failure_policy: MatchingFailurePolicy;
}

export const defaultCameraMatchingOptions: CameraMatchingOptions = {
    automatically_match: true,
    failure_policy: MatchingFailurePolicy.Continue,
};
