export enum DecoderCommand { Open = 'open', OpenUrl = 'open_url', Read = 'read' }
export enum DecoderReply { Ready = 'ready', Frame = 'frame', Error = 'error' }
export type DecoderRequest =
    | {kind: DecoderCommand.Open; file: File; budgetBytes: number}
    | {kind: DecoderCommand.OpenUrl; url: string; budgetBytes: number; encodedBudgetBytes: number}
    | {kind: DecoderCommand.Read; ordinal: number};
export type DecoderResponse =
    | {kind: DecoderReply.Ready; codec: string; frameCount: number; fps: number}
    | {kind: DecoderReply.Error; message: string}
    | {kind: DecoderReply.Frame; ordinal: number; bitmap: ImageBitmap;
        cacheHit: boolean; decoded: number; restarts: number; cacheBytes: number};
