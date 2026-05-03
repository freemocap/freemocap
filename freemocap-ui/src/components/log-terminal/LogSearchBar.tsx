import React from 'react';
import {Box, TextField, useTheme} from '@mui/material';
import {Search as SearchIcon} from '@mui/icons-material';
import {useTranslation} from 'react-i18next';

interface Props {
    searchText: string;
    onSearchChange: (text: string) => void;
}

export const LogSearchBar: React.FC<Props> = ({searchText, onSearchChange}) => {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <Box sx={{p: 1, borderBottom: '1px solid', borderColor: theme.palette.divider}}>
            <TextField
                size="small"
                fullWidth
                placeholder={t('searchLogs')}
                value={searchText}
                onChange={(e) => onSearchChange(e.target.value)}
                InputProps={{
                    startAdornment: <SearchIcon sx={{mr: 1, color: 'text.secondary'}}/>,
                }}
            />
        </Box>
    );
};
