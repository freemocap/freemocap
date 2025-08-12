import {CurrentFramerateSchema} from "@/store/slices/framerateTrackerSlice";
import {z} from 'zod'

export const BaseWebsocketMessageSchema = z.object({
    message_type: z.string(),
});
// Framerate update message schema
export const FramerateUpdateWebsocketMessageSchema = BaseWebsocketMessageSchema.extend({
    message_type: z.literal("framerate_update"),
    camera_group_id: z.string(),
    backend_framerate: CurrentFramerateSchema,
    frontend_framerate: CurrentFramerateSchema,
});



// Log record message schema - matching the Python LogRecordModel
export const LogRecordWebsocketMessageSchema = BaseWebsocketMessageSchema.extend({
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




// Add more message schemas as needed
// const OtherMessageTypeSchema = BaseMessageSchema.extend({
//     message_type: z.literal("other_message_type"),
//     // other fields...
// });

// Union of all message types
export const WebSocketMessageSchema = z.discriminatedUnion("message_type", [
    FramerateUpdateWebsocketMessageSchema,
    LogRecordWebsocketMessageSchema,
    // Add more message schemas to the union as needed
]);

export type WebSocketMessage = z.infer<typeof WebSocketMessageSchema>;
export type FramerateUpdateWebSocketMessage = z.infer<typeof FramerateUpdateWebsocketMessageSchema>;
