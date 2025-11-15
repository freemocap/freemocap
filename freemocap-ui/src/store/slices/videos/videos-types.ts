export interface VideoFile {
    name: string;
    path: string;
    size?: number;
    duration?: number;
    thumbnail?: string;
}

export interface VideosState {
    folder: string;
    files: VideoFile[];
    selectedFile: VideoFile | null;
    isLoading: boolean;
    error: string | null;
    playbackState: {
        isPlaying: boolean;
        currentTime: number;
        duration: number;
        volume: number;
        playbackRate: number;
    };
}
