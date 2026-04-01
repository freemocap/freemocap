import React, { useCallback } from "react";
import {
  Box,
  Chip,
  Container,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import type { SelectChangeEvent } from "@mui/material/Select";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import VerifiedIcon from "@mui/icons-material/Verified";
import TranslateIcon from "@mui/icons-material/Translate";
import PaletteIcon from "@mui/icons-material/Palette";
import InfoIcon from "@mui/icons-material/Info";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import {EXTERNAL_URLS} from "@/constants/external-urls";
import { useTranslation } from "react-i18next";
import { Footer } from "@/components/ui-components/Footer";
import { useAppDispatch, useAppSelector } from "@/store";
import { themeModeSet } from "@/store/slices/theme";
import {
  localeChanged,
  showTranslationIndicatorToggled,
  selectLocale,
  selectShowTranslationIndicator,
} from "@/store/slices/settings";
import {
  SUPPORTED_LOCALES,
  getTranslationSource,
} from "@/i18n";
import type { SupportedLocale } from "@/i18n";
import type { ThemeMode } from "@/store/slices/theme";
import * as Flags from "country-flag-icons/react/3x2";
import {CherokeeFlag} from "@/components/languages/custom-flag-icons/CherokeeFlag";
import { VersionChip } from "@/components/ui-components/VersionChip";

const FlagIcon: React.FC<{ countryCode: string }> = ({ countryCode }) => {
  if (countryCode === "CHEROKEE") return <CherokeeFlag />;
  const Flag = Flags[countryCode as keyof typeof Flags];
  if (!Flag) return null;
  return <Flag style={{ width: 20, height: 14, borderRadius: 2, flexShrink: 0 }} />;
};

const SectionHeader: React.FC<{
  icon: React.ReactNode;
  title: string;
}> = ({ icon, title }) => {
  const theme = useTheme();
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        mb: 2,
        mt: 1,
      }}
    >
      <Box sx={{ color: theme.palette.primary.main, display: "flex" }}>
        {icon}
      </Box>
      <Typography variant="h6" sx={{ fontSize: 15, fontWeight: 600 }}>
        {title}
      </Typography>
    </Box>
  );
};

const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const isDark = theme.palette.mode === "dark";

  const currentLocale = useAppSelector(selectLocale);
  const showTranslationIndicator = useAppSelector(
    selectShowTranslationIndicator
  );
  const themeMode = useAppSelector((state) => state.theme.mode);
  const translationSource = getTranslationSource(currentLocale);

  const handleLocaleChange = useCallback(
    (event: SelectChangeEvent<string>) => {
      dispatch(localeChanged(event.target.value as SupportedLocale));
    },
    [dispatch]
  );

  const handleThemeChange = useCallback(
    (
      _event: React.MouseEvent<HTMLElement>,
      newMode: string | null
    ) => {
      if (newMode !== null) {
        dispatch(themeModeSet(newMode as ThemeMode));
      }
    },
    [dispatch]
  );

  const handleTranslationIndicatorToggle = useCallback(() => {
    dispatch(showTranslationIndicatorToggled());
  }, [dispatch]);

  const sourceLabel =
    translationSource === "human-authored"
      ? t("humanTranslated")
      : translationSource === "human-validated"
        ? t("humanValidated")
        : t("aiTranslated");

  const sourceIcon =
    translationSource === "ai-generated" ? (
      <SmartToyIcon sx={{ fontSize: 14 }} />
    ) : (
      <VerifiedIcon sx={{ fontSize: 14 }} />
    );

  const sourceColor =
    translationSource === "ai-generated"
      ? "warning"
      : translationSource === "human-validated"
        ? "success"
        : ("info" as const);

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: isDark
          ? theme.palette.background.default
          : theme.palette.background.paper,
        overflow: "auto",
      }}
    >
      <Container maxWidth="sm" sx={{ py: 3, flex: 1 }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 700, mb: 3 }}
        >
          {t("settings")}
        </Typography>

        {/* Language & Localization */}
        <Paper
          elevation={isDark ? 2 : 1}
          sx={{
            p: 2.5,
            mb: 2,
            backgroundColor: isDark
              ? theme.palette.background.paper
              : "#fff",
          }}
        >
          <SectionHeader
            icon={<TranslateIcon fontSize="small" />}
            title={t("languageSettings")}
          />

          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 2,
                flexWrap: "wrap",
              }}
            >
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="settings-language-label">
                  {t("language")}
                </InputLabel>
                <Select
                  labelId="settings-language-label"
                  value={currentLocale}
                  label={t("language")}
                  onChange={handleLocaleChange}
                  sx={{ fontSize: 13 }}
                >
                  {Object.entries(SUPPORTED_LOCALES).map(
                    ([code, { label, dir, flag }]) => (
                      <MenuItem key={code} value={code}>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <FlagIcon countryCode={flag} />
                          <Typography
                            component="span"
                            sx={{ fontSize: 13, direction: dir }}
                          >
                            {label}
                          </Typography>
                          <Typography
                            component="span"
                            sx={{ fontSize: 11, color: "text.disabled", fontFamily: "monospace" }}
                          >
                            {code}
                          </Typography>
                        </Box>
                      </MenuItem>
                    )
                  )}
                </Select>
              </FormControl>

              {translationSource !== "human-authored" && (
                <Tooltip
                  title={
                    translationSource === "ai-generated"
                      ? t("aiTranslatedTooltip")
                      : t("humanValidatedTooltip")
                  }
                  arrow
                >
                  <Chip
                    icon={sourceIcon}
                    label={sourceLabel}
                    size="small"
                    color={sourceColor}
                    variant="outlined"
                    clickable
                    component="a"
                    href={EXTERNAL_URLS.TRANSLATION_LOCALES}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{
                      height: 24,
                      fontSize: 11,
                      cursor: "pointer",
                      "& .MuiChip-icon": { fontSize: 14 },
                    }}
                  />
                </Tooltip>
              )}
            </Box>

            {translationSource === "ai-generated" && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: 11 }}
              >
                {t("aiTranslatedTooltip")}{" "}
                <Typography
                  component="a"
                  href={EXTERNAL_URLS.TRANSLATING_GUIDE}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="caption"
                  sx={{
                    fontSize: 11,
                    color: "primary.main",
                    textDecoration: "underline",
                    cursor: "pointer",
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.3,
                  }}
                >
                  {t("helpTranslate")} <OpenInNewIcon sx={{fontSize: 11}} />
                </Typography>
              </Typography>
            )}

            <FormControlLabel
              control={
                <Switch
                  checked={showTranslationIndicator}
                  onChange={handleTranslationIndicatorToggle}
                  size="small"
                />
              }
              label={
                <Box>
                  <Typography variant="body2" sx={{ fontSize: 13 }}>
                    {t("showTranslationIndicator")}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontSize: 11 }}
                  >
                    {t("showTranslationIndicatorDescription")}
                  </Typography>
                </Box>
              }
            />
          </Box>
        </Paper>

        {/* Appearance */}
        <Paper
          elevation={isDark ? 2 : 1}
          sx={{
            p: 2.5,
            mb: 2,
            backgroundColor: isDark
              ? theme.palette.background.paper
              : "#fff",
          }}
        >
          <SectionHeader
            icon={<PaletteIcon fontSize="small" />}
            title={t("appearance")}
          />

          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Typography variant="body2" sx={{ fontSize: 13 }}>
              {t("themeMode")}
            </Typography>
            <ToggleButtonGroup
              value={themeMode}
              exclusive
              onChange={handleThemeChange}
              size="small"
              sx={{
                "& .MuiToggleButton-root": {
                  py: 0.5,
                  px: 2,
                  fontSize: 12,
                },
                "& .MuiToggleButton-root.Mui-selected": {
                  backgroundColor: theme.palette.primary.dark,
                  color: theme.palette.primary.contrastText,
                  "&:hover": {
                    backgroundColor: theme.palette.primary.light,
                  },
                },
              }}
            >
              <ToggleButton value="light">{t("lightMode")}</ToggleButton>
              <ToggleButton value="dark">{t("darkMode")}</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Paper>

        {/* About */}
        <Paper
          elevation={isDark ? 2 : 1}
          sx={{
            p: 2.5,
            mb: 2,
            backgroundColor: isDark
              ? theme.palette.background.paper
              : "#fff",
          }}
        >
          <SectionHeader
            icon={<InfoIcon fontSize="small" />}
            title={t("about")}
          />

          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Typography variant="body2" sx={{ fontSize: 13 }}>
              {t("appName")} — {t("welcomeSubtitle")}
            </Typography>
            <VersionChip variant="full" />
          </Box>
        </Paper>
      </Container>

      <Divider />
      <Box component="footer" sx={{ p: 1 }}>
        <Footer />
      </Box>
    </Box>
  );
};

export default SettingsPage;
