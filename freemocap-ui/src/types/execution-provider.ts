/** null = auto-select the best available provider. */
export type ExecutionProviderName = "trt" | "cuda" | "coreml" | "directml" | "cpu";

export const EXECUTION_PROVIDERS: { label: string; value: ExecutionProviderName | null }[] = [
    { label: "Auto", value: null },
    { label: "TensorRT", value: "trt" },
    { label: "CUDA", value: "cuda" },
    { label: "CoreML", value: "coreml" },
    { label: "DirectML", value: "directml" },
    { label: "CPU", value: "cpu" },
];
