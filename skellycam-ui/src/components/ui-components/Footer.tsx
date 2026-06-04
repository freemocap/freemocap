import * as React from "react";
import { useTranslation } from "react-i18next";
import { EXTERNAL_URLS } from "@/constants/external-urls";

export const Footer = function () {
    const { t } = useTranslation();

    return (
           
        <p className="pos-abs footer-content text sm text-gray text-center">
            <a
                className="text-gray flex flex-row gap-1"
                href={EXTERNAL_URLS.GITHUB_ORG}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
            >
            {t('footerWith') + ' '}
            <span className="flex-inline icon icon-size-20 donate-icon"></span>
            {/* <a
                className="text-gray flex flex-row gap-1"
                href={EXTERNAL_URLS.GITHUB_ORG}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
            > */}
                
            {/* </a> */}
            {' ' + t('footerFrom') + ' '}
         
                {t('footerOrgName')}
            
            {' '}{new Date().getFullYear()}
            <span className="flex-inline icon icon-size-20 externallink-icon"></span>
            </a>
        </p>
        
            //  <ButtonSm
            //                     iconClass=""
            //                     text={t('roadmap')}
            //                     rightSideIcon="externallink"
            //                     textColor="text-gray"
            //                     onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
            //                 />
    );
};
