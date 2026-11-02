/** Execution projection leaves the user's human reconstruction/export settings intact. */
export function dlcPosthocExecutionSettings(detectorType: string, provider: 'cpu' | 'cuda' = 'cpu') {
    return detectorType === 'dlc' ? {
        startStage: 'observations' as const, stopStage: 'observations' as const,
        executionProvider: provider, graphExecutionProvider: provider,
        exportToBlender: false, charucoTrackingEnabled: false,
        scientificExports: {formats: [], data: []}, calibrationTomlPath: null,
    } : {};
}
