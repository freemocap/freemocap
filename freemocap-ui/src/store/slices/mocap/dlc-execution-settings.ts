/** Execution projection leaves the user's human reconstruction/export settings intact. */
export function dlcPosthocExecutionSettings(detectorType: string, provider: 'cpu' | 'cuda' = 'cpu', triangulate = false, geometryPath?: string | null) {
    return detectorType === 'dlc' ? {
        startStage: 'observations' as const, stopStage: triangulate ? (geometryPath ? 'reconstruction' as const : 'filtering' as const) : 'observations' as const,
        executionProvider: provider, graphExecutionProvider: provider,
        exportToBlender: false, charucoTrackingEnabled: false,
        scientificExports: {formats: [], data: []},
        ...(triangulate ? {} : {calibrationTomlPath: null}),
    } : {};
}
