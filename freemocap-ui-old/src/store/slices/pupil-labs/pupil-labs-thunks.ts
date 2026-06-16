import { createAsyncThunk } from "@reduxjs/toolkit";
import { RootState } from "@/store/types";
import { serverUrls } from "@/services";
import { getDetailedErrorMessage } from "@/store/slices/thunk-helpers";

// ---------------------------------------------------------------------------
// Connect
// ---------------------------------------------------------------------------

interface ConnectResult {
    success: boolean;
    message?: string | null;
}

export const connectPupilLabs = createAsyncThunk<
    ConnectResult,
    { host?: string; port?: number; eyeIds?: number[] } | void,
    { state: RootState; rejectValue: string }
>("pupilLabs/connect", async (arg, { rejectWithValue }) => {
    try {
        const response = await fetch(serverUrls.endpoints.pupilConnect, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                pupilCaptureHost: arg?.host ?? "localhost",
                pupilCapturePort: arg?.port ?? 50020,
                eyeIds: arg?.eyeIds ?? [0, 1],
            }),
        });

        if (!response.ok) {
            return rejectWithValue(await getDetailedErrorMessage(response));
        }
        const data = await response.json();
        return { success: !!data.success, message: data.message ?? null };
    } catch (e) {
        return rejectWithValue(
            e instanceof Error ? e.message : "Unknown error connecting to Pupil Capture",
        );
    }
});

// ---------------------------------------------------------------------------
// Disconnect
// ---------------------------------------------------------------------------

export const disconnectPupilLabs = createAsyncThunk<
    ConnectResult,
    void,
    { state: RootState; rejectValue: string }
>("pupilLabs/disconnect", async (_, { rejectWithValue }) => {
    try {
        const response = await fetch(serverUrls.endpoints.pupilDisconnect, {
            method: "POST",
        });

        if (!response.ok) {
            return rejectWithValue(await getDetailedErrorMessage(response));
        }
        const data = await response.json();
        return { success: !!data.success, message: data.message ?? null };
    } catch (e) {
        return rejectWithValue(
            e instanceof Error ? e.message : "Unknown error disconnecting from Pupil Capture",
        );
    }
});

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

interface StatusResult {
    connected: boolean;
    recording: boolean;
}

export const getPupilLabsStatus = createAsyncThunk<
    StatusResult,
    void,
    { state: RootState; rejectValue: string }
>("pupilLabs/status", async (_, { rejectWithValue }) => {
    try {
        const response = await fetch(serverUrls.endpoints.pupilStatus);

        if (!response.ok) {
            return rejectWithValue(await getDetailedErrorMessage(response));
        }
        const data = await response.json();
        return {
            connected: !!data.connected,
            recording: !!data.recording,
        };
    } catch (e) {
        return rejectWithValue(
            e instanceof Error ? e.message : "Unknown error fetching Pupil Labs status",
        );
    }
});
