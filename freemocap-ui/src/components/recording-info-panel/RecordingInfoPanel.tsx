// skellycam-ui/src/components/recording-info-panel/RecordingInfoPanel.tsx
import React, {useEffect, useState} from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  alpha,
  Box,
  IconButton,
  Paper,
  Stack,
  Typography,
  useTheme
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import VideocamIcon from '@mui/icons-material/Videocam';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {
  RecordingSettingsSection
} from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";
import {
  StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {
  DelayRecordingStartControl
} from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import {
  FullRecordingPathPreview
} from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import {
  BaseRecordingDirectoryInput
} from "@/components/recording-info-panel/recording-subcomponents/BaseRecordingDirectoryInput";
import {RecordingNamePreview} from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import {startRecording, stopRecording} from "@/store/thunks/start-stop-recording-thunks";
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";

export const RecordingInfoPanel: React.FC = () => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector(state => state.recordingStatus.currentRecordingInfo);

  // Local UI state
  const [showSettings, setShowSettings] = useState(false);
  const [createSubfolder, setCreateSubfolder] = useState(false);
  const [useDelayStart, setUseDelayStart] = useState(false);
  const [delaySeconds, setDelaySeconds] = useState(3);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [recordingTag, setRecordingTag] = useState('');

  // Local recording naming preferences
  const [useTimestamp, setUseTimestamp] = useState(true);
  const [useIncrement, setUseIncrement] = useState(false);
  const [currentIncrement, setCurrentIncrement] = useState(1);
  const [baseName, setBaseName] = useState('recording');
  const [customSubfolderName, setCustomSubfolderName] = useState('');

  // replace ~ with user's home directory
// replace ~ with user's home directory
useEffect(() => {
  if (recordingInfo?.recordingDirectory?.startsWith('~')) {
    window.electronAPI.getHomeDirectory().then(
      (homePath: string) => {
        const updatedDirectory = recordingInfo.recordingDirectory.replace('~', homePath);
        dispatch(setRecordingInfo({ recordingDirectory: updatedDirectory }));
      }
    );
  }
}, [recordingInfo, dispatch]);

  // Handle countdown timer
  useEffect(() => {
    if (countdown !== null && countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (countdown === 0) {
      handleStartRecording();
      setCountdown(null);
    }
  }, [countdown]);

  const getTimestampString = (): string => {
    const now = new Date();
    
    // Format date in local time with timezone info
    const dateOptions: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZoneName: 'shortOffset'
    };
    
    // Get formatted parts
    const formatter = new Intl.DateTimeFormat('en-US', dateOptions);
    const parts = formatter.formatToParts(now);
    
    // Create a map of the parts for easy access
    const partMap: Record<string, string> = {};
    parts.forEach(part => {
      partMap[part.type] = part.value;
    });
    
    // Build the timestamp string in a filename-friendly format
    const timestamp = `${partMap.year}-${partMap.month}-${partMap.day}_${partMap.hour}-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(':', '')}`;
    
    return timestamp;
  };

  const buildRecordingName = (): string => {
    const parts: string[] = [];

    // Base name component
    if (useTimestamp) {
      parts.push(getTimestampString());
    } else {
      parts.push(baseName);
    }

    // Add tag if present
    if (recordingTag) {
      parts.push(recordingTag);
    }

    return parts.join('_');
  };

  const handleStartRecording = () => {
    console.log('Starting recording...');

    const recordingName = buildRecordingName();
    const subfolderName = createSubfolder ? (customSubfolderName || getTimestampString()) : '';
    const recordingPath = createSubfolder
      ? `${recordingInfo.recordingDirectory}/${subfolderName}`
      : recordingInfo.recordingDirectory;

    console.log('Recording path:', recordingPath);
    console.log('Recording name:', recordingName);

    if (useIncrement) {
      setCurrentIncrement(prev => prev + 1);
    }

    dispatch(startRecording({
      recordingName,
      recordingDirectory: recordingPath
    }));
  };

  const handleButtonClick = () => {
    if (recordingInfo.isRecording) {
      console.log('Stopping recording...');
      dispatch(stopRecording());
    } else if (useDelayStart) {
      console.log(`Starting countdown from ${delaySeconds} seconds`);
      setCountdown(delaySeconds);
    } else {
      handleStartRecording();
    }
  };

  const [expanded, setExpanded] = useState(true);

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, isExpanded) => setExpanded(isExpanded)}
      sx={{
        borderRadius: 2,
        '&:before': { display: 'none' },
        boxShadow: theme.shadows[3]
      }}
    >
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        backgroundColor: recordingInfo.isRecording ? theme.palette.error.main : theme.palette.primary.main,
        borderTopLeftRadius: 8,
        borderBottomLeftRadius: 8,
      }}>
        <AccordionSummary
          expandIcon={<ExpandMoreIcon sx={{ color: theme.palette.primary.contrastText }} />}
          sx={{
            flex: 1,
            color: theme.palette.primary.contrastText,
            '&:hover': {
              backgroundColor: recordingInfo.isRecording ? theme.palette.error.light : theme.palette.primary.light,
            }
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <VideocamIcon />
            <Typography variant="subtitle1" fontWeight="medium">
              {recordingInfo.isRecording ? 'Recording in Progress...' : 'Record Videos'}
            </Typography>
          </Stack>
        </AccordionSummary>

        <Box sx={{ pr: 2 }}>
          <StartStopRecordingButton
            isRecording={recordingInfo.isRecording}
            countdown={countdown}
            onClick={handleButtonClick}
          />
        </Box>

        <Box sx={{ pr: 2 }}>
          <IconButton
            onClick={() => {
                setShowSettings(!showSettings);
                setExpanded(true);
            }}
            sx={{
              color: showSettings
                ? theme.palette.primary.contrastText
                : alpha(theme.palette.primary.contrastText, 0.7)
            }}
          >
            <SettingsIcon />
          </IconButton>
        </Box>
      </Box>

      <AccordionDetails sx={{ p: 2, bgcolor: 'background.default' }}>
        <Paper
          elevation={0}
          sx={{
            bgcolor: 'background.paper',
            borderRadius: 2,
            overflow: 'hidden',
            p: 2
          }}
        >
          <Stack spacing={2}>
            <FullRecordingPathPreview
              directory={recordingInfo.recordingDirectory}
              filename={buildRecordingName()}
              subfolder={createSubfolder ? (customSubfolderName || getTimestampString()) : undefined}
            />

            {showSettings && (
              <>
                <DelayRecordingStartControl
                  useDelay={useDelayStart}
                  delaySeconds={delaySeconds}
                  onDelayToggle={setUseDelayStart}
                  onDelayChange={setDelaySeconds}
                />

                <BaseRecordingDirectoryInput
                  value={recordingInfo.recordingDirectory}
                />

                <RecordingNamePreview
                  name={buildRecordingName()}
                  tag={recordingTag}
                  isRecording={recordingInfo.isRecording}
                  onTagChange={setRecordingTag}
                />

                <RecordingSettingsSection
                  useTimestamp={useTimestamp}
                  baseName={baseName}
                  useIncrement={useIncrement}
                  currentIncrement={currentIncrement}
                  createSubfolder={createSubfolder}
                  customSubfolderName={customSubfolderName}
                  onUseTimestampChange={setUseTimestamp}
                  onBaseNameChange={setBaseName}
                  onUseIncrementChange={setUseIncrement}
                  onIncrementChange={setCurrentIncrement}
                  onCreateSubfolderChange={setCreateSubfolder}
                  onCustomSubfolderNameChange={setCustomSubfolderName}
                />
              </>
            )}
          </Stack>
        </Paper>
      </AccordionDetails>
    </Accordion>
  );
};
