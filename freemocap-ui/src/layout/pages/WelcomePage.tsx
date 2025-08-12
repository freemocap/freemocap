import React from 'react';
import {Box, Button, Typography, Container, Paper, Fade, Grow, darken} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@mui/material/styles';
import VideocamIcon from '@mui/icons-material/Videocam';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import { Copyright } from '@/components/ui-components/Copyright';

const WelcomePage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();

  return (
    <Container maxWidth="md" sx={{
      height: '100%',
      width: '100%',
      bgcolor: theme.palette.background.default,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      py: 4
    }}>
      <Fade in={true} timeout={800}>
        <Paper
          elevation={6}
          sx={{
            p: { xs: 3, sm: 5 },
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
            backgroundColor: theme.palette.background.paper,
            mx: 'auto',
            borderRadius: 3,
            boxShadow: theme.palette.mode === 'dark'
              ? '0 8px 32px rgba(0, 0, 0, 0.5)'
              : '0 8px 32px rgba(0, 0, 0, 0.1)',
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          {/* Background accent */}
          <Box sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '8px',
            background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
          }} />

          <Grow in={true} timeout={1000}>
            <Box
              sx={{
                width: 180,
                height: 180,
                mb: 4,
                mt: 2,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                transition: 'transform 0.3s ease-in-out',
                '&:hover': {
                  transform: 'scale(1.05)'
                }
              }}
            >
              <img
                src="/skellycam-logo.png"
                alt="SkellyCam Logo"
                style={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                  filter: theme.palette.mode === 'dark' ? 'drop-shadow(0 0 10px rgba(255,255,255,0.2))' : 'drop-shadow(0 0 10px rgba(0,0,0,0.1))'
                }}
              />
            </Box>
          </Grow>

          <Typography
            variant="h3"
            component="h1"
            gutterBottom
            sx={{
              fontWeight: 'bold',
              textAlign: 'center',
              background: theme.palette.text.primary,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              textFillColor: 'transparent',
              mb: 2
            }}
          >
            Welcome to SkellyCam
          </Typography>

          <Typography
            variant="subtitle1"
            color="text.secondary"
            sx={{
              mb: 5,
              textAlign: 'center',
              maxWidth: '80%',
              fontSize: '1.1rem'
            }}
          >
            Record and View Synchronized Videos
          </Typography>

          <Box sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 3,
            width: '100%',
            mt: 2,
            justifyContent: 'center'
          }}>
            <Button
              variant="contained"
              size="large"
              fullWidth
              startIcon={<VideocamIcon />}
              onClick={() => navigate('/cameras')}
              sx={{
                py: 2.5,
                fontSize: '1.1rem',
                backgroundColor: theme.palette.primary.main,
                borderRadius: 2,
                transition: 'all 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-3px)',
                  boxShadow: theme.palette.mode === 'dark'
                    ? '0 7px 15px rgba(0, 0, 0, 0.4)'
                    : '0 7px 15px rgba(0, 0, 0, 0.2)',
                }
              }}
            >
              Record New Videos
            </Button>
            <Button
              variant="contained"
              size="large"
              fullWidth
              startIcon={<VideoLibraryIcon />}
              onClick={() => navigate('/videos')}
              sx={{
                py: 2.5,
                fontSize: '1.1rem',
                backgroundColor: darken(theme.palette.secondary.main, 0.2),
                borderRadius: 2,
                transition: 'all 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-3px)',
                  boxShadow: theme.palette.mode === 'dark'
                    ? '0 7px 15px rgba(0, 0, 0, 0.4)'
                    : '0 7px 15px rgba(0, 0, 0, 0.2)',
                }
              }}
            >
              Load Synchronized Videos
            </Button>
          </Box>

          <Box component="footer" sx={{p: 3}}>
                    <Copyright />
                </Box>
        </Paper>
      </Fade>
    </Container>
  );
};

export default WelcomePage;
