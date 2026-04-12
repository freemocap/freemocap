import {useAppDispatch} from "@/store";
import {useTheme} from "@mui/material/styles";
import {useTranslation} from "react-i18next";
import {Box, Button} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import SlideshowIcon from '@mui/icons-material/Slideshow';
import {useNavigate} from "react-router-dom";

export const PageTabButtons = () => {
    const theme = useTheme();
    const navigate = useNavigate();

    const {t} = useTranslation();

    return (
        <Box sx={{
            display: 'flex',
            gap: 0.5,
            px: 0.75,
            py: 0.75,
            borderBottom: theme.palette.mode === 'dark'
                ? '1px solid rgba(255,255,255,0.08)'
                : '1px solid rgba(0,0,0,0.08)',
        }}>
            <Button
                variant={location.pathname === '/cameras' ? 'contained' : 'outlined'}
                size="small"
                startIcon={<VideocamIcon sx={{fontSize: 16}}/>}
                onClick={() => navigate('/cameras')}
                fullWidth
                sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    py: 0.75,
                    ...(location.pathname === '/cameras' ? {
                        backgroundColor: theme.palette.success.main,
                        color: '#fff',
                        '&:hover': {backgroundColor: theme.palette.success.dark},
                    } : {
                        borderColor: theme.palette.divider,
                        color: theme.palette.text.secondary,
                        '&:hover': {
                            borderColor: theme.palette.success.main,
                            color: theme.palette.success.main,
                            backgroundColor: theme.palette.mode === 'dark'
                                ? 'rgba(76,175,80,0.08)'
                                : 'rgba(76,175,80,0.04)',
                        },
                    }),
                }}
            >
                Streaming
            </Button>
            <Button
                variant={location.pathname === '/playback' ? 'contained' : 'outlined'}
                size="small"
                startIcon={<SlideshowIcon sx={{fontSize: 16}}/>}
                onClick={() => navigate('/playback')}
                fullWidth
                sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    py: 0.75,
                    ...(location.pathname === '/playback' ? {
                        backgroundColor: theme.palette.info.main,
                        color: '#fff',
                        '&:hover': {backgroundColor: theme.palette.info.dark},
                    } : {
                        borderColor: theme.palette.divider,
                        color: theme.palette.text.secondary,
                        '&:hover': {
                            borderColor: theme.palette.info.main,
                            color: theme.palette.info.main,
                            backgroundColor: theme.palette.mode === 'dark'
                                ? 'rgba(41,182,246,0.08)'
                                : 'rgba(41,182,246,0.04)',
                        },
                    }),
                }}
            >
                {t('videoPlayback')}
            </Button>
        </Box>

    )
}
