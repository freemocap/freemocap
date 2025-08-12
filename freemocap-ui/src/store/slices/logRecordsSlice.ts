import type {PayloadAction} from "@reduxjs/toolkit";
import {createSlice} from "@reduxjs/toolkit"
import {z} from "zod";


// Updated to match the server's LogRecordModel
export const LogRecordSchema = z.object({
    name: z.string(),
    msg: z.string().nullable().default(""),
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
    type: z.string(),
});
export type LogRecord = z.infer<typeof LogRecordSchema>;

export const IncomingLogsSchema = z.object({
    logs: z.array(LogRecordSchema),
});

export type IncomingLogs = z.infer<typeof IncomingLogsSchema>;

interface LogsState {
    entries: LogRecord[]
}
const initialLogRecord: LogRecord = {
    name: "initial",
    msg: "Log entry initialized",
    args: [],
    levelname: "DEBUG",
    levelno: 10,
    filename: "filename",
    pathname: "pathname",
    module: "module",
    exc_info: "exc_info",
    exc_text: "exc_text",
    stack_info: "stack_info",
    lineno: 0,
    funcName: "funcName",
    created: 0,
    msecs: 0,
    relativeCreated: 0,
    thread: 0,
    threadName: "threadName",
    processName: "processName",
    process: 0,
    delta_t: "0.000",
    message: "Initial log message",
    asctime: new Date().toISOString(),
    formatted_message: "Initial log message",
    type: "log",
}
const initialState: LogsState = {
    entries: [initialLogRecord],
}
const MAX_LOG_ENTRIES = 300
export const logRecordsSlice = createSlice({
    name: "logs",
    initialState,
    reducers: {
        addLog: (state,
                 action: PayloadAction<LogRecord>) => {
            const newLogEntry: LogRecord = {
                ...action.payload,
            }

            // if we're at the limit, remove the oldest entry first
            if (state.entries.length >= MAX_LOG_ENTRIES) {
                state.entries.shift() // Remove the oldest log entry
            }

            state.entries.push(newLogEntry)
        },
        addLogs: (state,
                    action: PayloadAction<IncomingLogs>) => {
            const newLogs: LogRecord[] = action.payload.logs
            // Add new logs to the state, ensuring we don't exceed the max limit
            for (const log of newLogs) {
                const newLogEntry: LogRecord = {
                    ...log,
                }

                // if we're at the limit, remove the oldest entry first
                if (state.entries.length >= MAX_LOG_ENTRIES) {
                    state.entries.shift() // Remove the oldest log entry
                }

                state.entries.push(newLogEntry)
            }
        }
    },

})

export const {addLog, addLogs} = logRecordsSlice.actions
export default logRecordsSlice.reducer
