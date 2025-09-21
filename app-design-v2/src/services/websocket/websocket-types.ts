import { z } from 'zod';

// Import from framerate types
export const CurrentFramerateSchema = z.object({
    mean: z.number(),
    std: z.number(),
    current: z.number(),
});

export const FramerateUpdateMessageSchema = z.object({
    message_type: z.literal("framerate_update"),
    camera_group_id: z.string(),
    backend_framerate: CurrentFramerateSchema,
    frontend_framerate: CurrentFramerateSchema,
});

// Log record message schema - matching the Python LogRecordModel
export const LogRecordMessageSchema = z.object({
    message_type: z.literal("log_record"),
    name: z.string(),
    msg: z.string().nullable(),
    args: z.array(z.any()),
    levelname: z.string(),
    levelno: z.number(),
    pathname: z.string(),
    filename: z.string(),
    module: z.string(),
    exc_info: z.string().nullable(),
    exc_text: z.string().nullable(),
    stack_info: z.string().nullable(),
    lineno: z.number(),
    funcName: z.string(),
    created: z.number(),
    msecs: z.number(),
    relativeCreated: z.number(),
    thread: z.number(),
    threadName: z.string(),
    processName: z.string(),
    process: z.number(),
    delta_t: z.string(),
    message: z.string(),
    asctime: z.string(),
    formatted_message: z.string(),
    type: z.string()
});

export const WebSocketMessageSchema = z.discriminatedUnion("message_type", [
    FramerateUpdateMessageSchema,
    LogRecordMessageSchema,
]);

export type WebSocketMessage = z.infer<typeof WebSocketMessageSchema>;
export type FramerateUpdateMessage = z.infer<typeof FramerateUpdateMessageSchema>;
export type LogRecordMessage = z.infer<typeof LogRecordMessageSchema>;
