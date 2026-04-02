import React, { useCallback } from "react";
import {
    Box,
    IconButton,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import CastConnectedIcon from "@mui/icons-material/CastConnected";
import { useAppSelector } from "@/store/hooks";
import { selectServerSettings } from "@/store/slices/settings/settings-selectors";
import { useServer } from "@/services";

/**
 * Compact VMC output controls. Shows a toggle to enable/disable VMC
 * broadcasting and a port field. Patches are sent directly via the
 * WebSocket settings/patch protocol.
 */
export const VMCPanel: React.FC = () => {
    const theme = useTheme();
    const { send, isConnected } = useServer();
    const settings = useAppSelector(selectServerSettings);

    const vmcEnabled = settings?.vmc?.enabled ?? false;
    const vmcHost = settings?.vmc?.host ?? "127.0.0.1";
    const vmcPort = settings?.vmc?.port ?? 39539;

    const patchVMC = useCallback(
        (patch: Record<string, unknown>) => {
            send({ message_type: "settings/patch", patch: { vmc: patch } });
        },
        [send],
    );

    const handleToggle = useCallback(() => {
        patchVMC({ enabled: !vmcEnabled });
    }, [patchVMC, vmcEnabled]);

    const handlePortChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val) && val > 0 && val <= 65535) {
                patchVMC({ port: val });
            }
        },
        [patchVMC],
    );

    const handleHostChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const val = e.target.value.trim();
            if (val.length > 0) {
                patchVMC({ host: val });
            }
        },
        [patchVMC],
    );

    return (
        <Box
            sx={{
                position: "absolute",
                bottom: 16,
                right: 16,
                zIndex: 10,
                backgroundColor: theme.palette.background.paper,
                borderRadius: 2,
                px: 2,
                py: 1.5,
                boxShadow: 3,
                minWidth: 220,
                opacity: 0.92,
            }}
        >
            <Stack spacing={1}>
                <Stack direction="row" alignItems="center" spacing={1}>
                    <CastConnectedIcon
                        fontSize="small"
                        sx={{ color: vmcEnabled ? theme.palette.success.main : theme.palette.text.disabled }}
                    />
                    <Typography variant="subtitle2" sx={{ flexGrow: 1, fontWeight: 600 }}>
                        VMC Output
                    </Typography>
                    <Tooltip title={vmcEnabled ? "Disable VMC streaming" : "Enable VMC streaming"} arrow>
                        <Switch
                            size="small"
                            checked={vmcEnabled}
                            onChange={handleToggle}
                            disabled={!isConnected}
                        />
                    </Tooltip>
                </Stack>

                {vmcEnabled && (
                    <Stack direction="row" spacing={1}>
                        <Tooltip title="Target host (IP address)" arrow placement="bottom">
                            <TextField
                                label="Host"
                                size="small"
                                value={vmcHost}
                                onChange={handleHostChange}
                                disabled={!isConnected}
                                sx={{ flex: 2 }}
                                inputProps={{ style: { fontSize: 12 } }}
                                InputLabelProps={{ style: { fontSize: 12 } }}
                            />
                        </Tooltip>
                        <Tooltip title="UDP port (default 39539)" arrow placement="bottom">
                            <TextField
                                label="Port"
                                size="small"
                                type="number"
                                value={vmcPort}
                                onChange={handlePortChange}
                                disabled={!isConnected}
                                sx={{ flex: 1 }}
                                inputProps={{ min: 1, max: 65535, style: { fontSize: 12 } }}
                                InputLabelProps={{ style: { fontSize: 12 } }}
                            />
                        </Tooltip>
                    </Stack>
                )}
            </Stack>
        </Box>
    );
};
