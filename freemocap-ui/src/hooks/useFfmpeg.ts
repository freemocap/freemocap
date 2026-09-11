import {useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {detectFfmpeg, selectFfmpeg} from '@/store/slices/ffmpeg';

export function useFfmpeg() {
    const dispatch = useAppDispatch();
    const ffmpeg = useAppSelector(selectFfmpeg);

    useEffect(() => {
        if (ffmpeg.found === null && !ffmpeg.isDetecting) {
            void dispatch(detectFfmpeg());
        }
    }, [dispatch, ffmpeg.found, ffmpeg.isDetecting]);

    return {
        found: ffmpeg.found,
        ffmpegPath: ffmpeg.ffmpegPath,
        ffprobePath: ffmpeg.ffprobePath,
        message: ffmpeg.message,
        isDetecting: ffmpeg.isDetecting,
        error: ffmpeg.error,
    };
}
