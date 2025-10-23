export {};

declare global {
  interface Window {
    electronAPI: {
      selectDirectory: () => Promise<string | null>;
    };
  }
}
