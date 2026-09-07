import {z} from 'zod';
import {ENVELOPE} from '../server/transport/message-contract';

export enum PlaybackCommand {Range = 'range', Cancel = 'cancel', Close = 'close'}
export enum PlaybackEvent {Ready = 'playback_ready', Frame = 'playback_frame', End = 'playback_end', Failed = 'playback_failed'}
export enum PlaybackSource {Raw = 'synchronized', Annotated = 'annotated'}
const ordinal = z.number().int().nonnegative();
export const PlaybackMessage = z.discriminatedUnion('kind', [
    z.object({...ENVELOPE, kind: z.literal(PlaybackEvent.Ready), filenames: z.array(z.string()),
        frame_count: ordinal.positive(), decoded_group_bytes: ordinal.positive(), maximum_payload_bytes: ordinal.positive()}),
    z.object({...ENVELOPE, kind: z.literal(PlaybackEvent.Frame), generation: ordinal,
        frame_number: ordinal, image: z.instanceof(Uint8Array)}),
    z.object({...ENVELOPE, kind: z.literal(PlaybackEvent.End), generation: ordinal}),
    z.object({...ENVELOPE, kind: z.literal(PlaybackEvent.Failed), detail: z.string()}),
]);
export interface PlaybackLocation {socketUrl: string; source: PlaybackSource}


export enum PlaybackResolution {Preview = 'preview', Detail = 'detail'}
export const PLAYBACK_ENCODING = {
    [PlaybackResolution.Preview]: {scale: 0.5, jpeg_quality: 60},
    [PlaybackResolution.Detail]: {scale: 1, jpeg_quality: 90},
} as const;
