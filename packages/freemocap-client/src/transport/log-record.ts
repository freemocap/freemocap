// src/services/server/server-helpers/log-store.ts

import {z} from 'zod';

export const LogRecordSchema = z.object({
    name: z.string(),
    msg: z.string().nullable().default(""),
    args: z.array(z.any()),
    levelname: z.string(),
    levelno: z.number(),
    pathname: z.string(),
    filename: z.string(),
    module: z.string(),
    exc_info: z.string().nullable().default(null),
    exc_text: z.string().nullable().default(null),
    stack_info: z.string().nullable().default(null),
    lineno: z.number(),
    funcName: z.string(),
    created: z.number(),
    msecs: z.number(),
    relativeCreated: z.number(),
    // Python thread identifiers can use CBOR uint64, decoded as bigint on macOS.
    // Keep ordinary numeric IDs compatible and preserve larger IDs without rounding.
    thread: z.union([z.number(), z.string(), z.bigint()]).transform(value =>
        typeof value === 'bigint'
            ? (Number.isSafeInteger(Number(value)) ? Number(value) : value.toString())
            : value),
    threadName: z.string(),
    processName: z.string(),
    process: z.number(),
    delta_t: z.string(),
    message: z.string(),
    asctime: z.string(),
    formatted_message: z.string(),
    type: z.string(),
    // 'ui' for browser console logs, 'server' (default) for backend logs
    source: z.string().optional().default('server'),
});

export type LogRecord = z.infer<typeof LogRecordSchema>;
