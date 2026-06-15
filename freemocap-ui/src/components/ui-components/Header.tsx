import * as React from 'react';

export const Header = function () {
    return (
        <div className="header-panel top-header flex flex-row items-center pl-2 pr-2" style={{ minHeight: 40 }}>
            <h1 className="title text-white flex-1">FreeMocap</h1>
        </div>
    );
}

export default Header;
