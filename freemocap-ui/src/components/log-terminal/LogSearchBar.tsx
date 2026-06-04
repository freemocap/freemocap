import React from 'react';
import {useTranslation} from 'react-i18next';

interface Props {
    searchText: string;
    onSearchChange: (text: string) => void;
}

export const LogSearchBar: React.FC<Props> = ({searchText, onSearchChange}) => {
    const {t} = useTranslation();

    return (
        <div className="log-search-bar">
            <span className="icon search-icon icon-size-20"/>
            <div className="input-with-string" style={{flex: 1}}>
                <input
                    className="input-field text md"
                    placeholder={t('searchLogs')}
                    value={searchText}
                    onChange={(e) => onSearchChange(e.target.value)}
                />
            </div>
        </div>
    );
};
