/** null = prefer CUDA with platform fallback; trt is retained only for saved-config migration. */
export type ExecutionProviderName = "trt" | "cuda" | "coreml" | "directml" | "cpu";

export const EXECUTION_PROVIDERS: { label: string; value: ExecutionProviderName | null }[] = [
    { label: "Auto", value: null },
    { label: "CUDA", value: "cuda" },
    { label: "CoreML", value: "coreml" },
    { label: "DirectML", value: "directml" },
    { label: "CPU", value: "cpu" },
];
