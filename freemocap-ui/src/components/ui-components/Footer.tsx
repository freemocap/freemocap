import * as React from "react";
import {useTranslation} from "react-i18next";
import {EXTERNAL_URLS} from "@/constants/external-urls";

export const Footer = function () {
    const {t} = useTranslation();

    return (
        <p className="text sm text-gray text-center">
            {t('footerWith') + ' '}
            <a href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer">
                ❤️
            </a>
            {' ' + t('footerFrom') + ' '}
            <a href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer">
                {t('footerOrgName')}
            </a>
            {' '}{new Date().getFullYear()}
        </p>
    );
}
