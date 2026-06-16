import React, {useCallback} from "react";
import {useTranslation} from "react-i18next";
import {Box, Chip, FormControl, InputLabel, MenuItem, Select, Tooltip, Typography,} from "@mui/material";
import type {SelectChangeEvent} from "@mui/material/Select";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import VerifiedIcon from "@mui/icons-material/Verified";
import {EXTERNAL_URLS} from "@/constants/external-urls";
import {useAppDispatch, useAppSelector} from "@/store";
import {localeChanged, selectLocale, selectShowTranslationIndicator,} from "@/store/slices/locale";
import type {SupportedLocale} from "@/i18n";
import {getTranslationSource, SUPPORTED_LOCALES,} from "@/i18n";
import * as Flags from "country-flag-icons/react/3x2";
import {CherokeeFlag} from "@/components/languages/custom-flag-icons/CherokeeFlag";
import {YiddishFlag} from "@/components/languages/custom-flag-icons/YiddishFlag";

const FlagIcon: React.FC<{ countryCode: string }> = ({ countryCode }) => {
  if (countryCode === "CHEROKEE") return <CherokeeFlag />;
  if (countryCode === "YIDDISH") return <YiddishFlag />;
  const Flag = Flags[countryCode as keyof typeof Flags];
  if (!Flag) return null;
  return <Flag style={{ width: 20, height: 14, borderRadius: 2, flexShrink: 0 }} />;
};

export const LanguageSwitcher: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const currentLocale = useAppSelector(selectLocale);
  const showIndicator = useAppSelector(selectShowTranslationIndicator);
  const translationSource = getTranslationSource(currentLocale);

  const handleChange = useCallback(
    (event: SelectChangeEvent<string>) => {
      dispatch(localeChanged(event.target.value as SupportedLocale));
    },
    [dispatch]
  );

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
        display: "flex",
        alignItems: "center",
        gap: 1,
      }}
    >
      <FormControl size="small" sx={{
        minWidth: 200,
        "& .MuiInputLabel-root": {
          color: "text.secondary",
        },
        "& .MuiInputLabel-root.Mui-focused": {
          color: "text.primary",
        },
      }}>
        <InputLabel id="language-select-label">{t("language")}</InputLabel>
        <Select
          labelId="language-select-label"
          value={currentLocale}
          label={t("language")}
          onChange={handleChange}
          sx={{
            fontSize: 13,
            "& .MuiSelect-select": {
              py: 0.75,
            },
          }}
        >
          {Object.entries(SUPPORTED_LOCALES).map(([code, { label, englishName, dir, flag }]) => (
            <MenuItem key={code} value={code}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <FlagIcon countryCode={flag} />
                <Typography
                  component="span"
                  sx={{
                    fontSize: 13,
                    direction: dir,
                  }}
                >
                  {label}
                </Typography>
                {label !== englishName && (
                  <Typography
                    component="span"
                    sx={{
                      fontSize: 11,
                      color: "text.secondary",
                    }}
                  >
                    {englishName}
                  </Typography>
                )}
                <Typography
                  component="span"
                  sx={{
                    fontSize: 11,
                    color: "text.disabled",
                    fontFamily: "monospace",
                  }}
                >
                  {code}
                </Typography>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {showIndicator && translationSource !== "human-authored" && (
        <Tooltip
          title={
            translationSource === "ai-generated"
              ? t("aiTranslatedTooltip")
              : t("humanValidatedTooltip")
          }
          arrow
          placement="bottom"
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
              "& .MuiChip-icon": {
                fontSize: 14,
              },
            }}
          />
        </Tooltip>
      )}
    </Box>
  );
};
