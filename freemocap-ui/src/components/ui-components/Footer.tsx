import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import * as React from "react";
import {useTheme} from "@mui/material";
import {useTranslation} from "react-i18next";
import {EXTERNAL_URLS} from "@/constants/external-urls";

export const Footer = function () {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <Typography
            variant="body2"
            color={theme.palette.mode === 'dark' ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.45)"}
            align="center"
        >
            {t('footerWith') + ' '}
            <Link color="inherit" href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer"
                  sx={{display: 'inline-flex', alignItems: 'center', textDecoration: 'none'}}>
                ❤️
            </Link>{' ' + t('footerFrom') + ' '}
            <Link color="inherit" href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer"
                  sx={{display: 'inline-flex', alignItems: 'center', textDecoration: 'none', '&:hover': { textDecoration: 'underline' }}}>
                {t('footerOrgName')}
            </Link>{' '}
            {new Date().getFullYear()}
        </Typography>
    );
}
