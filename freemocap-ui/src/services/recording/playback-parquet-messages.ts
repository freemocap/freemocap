import {z} from 'zod';
import {PlaybackManifestSchema, PlaybackChannelDataSchema} from './playback-data';

export const PlaybackLoadRequestSchema = z.object({
    url: z.string().url(), manifest: PlaybackManifestSchema,
});
export const PlaybackLoadResultSchema = z.discriminatedUnion('success', [
    z.object({success: z.literal(true), runs: z.record(z.string(), z.array(PlaybackChannelDataSchema))}),
    z.object({success: z.literal(false), message: z.string()}),
]);
export type PlaybackLoadResult = z.infer<typeof PlaybackLoadResultSchema>;
