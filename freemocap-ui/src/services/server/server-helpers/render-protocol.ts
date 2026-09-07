export enum RenderCommand { Prepare = 'prepare', Present = 'present', Release = 'release' }
export enum RenderEvent { Prepared = 'prepared', Presented = 'presented', Failed = 'failed' }
export interface PreparedImage { id: number; width: number; height: number }
export type ScheduledRenderMessage =
    | {type: RenderCommand.Prepare; id: number; pixelBuffer: ArrayBuffer; width: number; height: number}
    | {type: RenderCommand.Present | RenderCommand.Release; id: number};
export type ScheduledRenderReply = {type: RenderEvent; id: number; detail?: string};
