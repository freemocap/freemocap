import React from "react";
import { ButtonSm, DropdownButton, ConnectionDropdown } from "./uicomponents";

const HeaderPanel: React.FC = () => {
  return (
    <div className="header-panel flex flex-row justify-content-space-between br-2 h-25">
      {/* Left Section */}
      <div className="flex left-section">
        {/* Uncomment if needed */}
        {/* <ButtonSm
          iconClass="loader-icon"
          text="Connecting..."
          rightSideIcon="dropdown"
          textColor="text-gray"
          onClick={() => console.log("Connect clicked")}
        /> */}
        <ConnectionDropdown />
      </div>

      {/* Right Section */}
      <div className="flex right-section gap-2">
        <ButtonSm
          iconClass="donate-icon"
          text="Support the freemocap"
          rightSideIcon="externallink"
          textColor="text-gray"
          onClick={() => console.log("Support freemocap clicked")}
        />

        <DropdownButton
          containerClassName="align-end"
          buttonProps={{
            text: "Help",
            rightSideIcon: "dropdown",
            textColor: "text-gray",
            iconClass: "",
            onClick: () => console.log("Help dropdown clicked"),
          }}
          dropdownItems={[
            <ButtonSm
              key="FreeMocap Guide"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="FreeMocap Guide"
              iconClass="learn-icon"
              onClick={() => console.log("FreeMocap Guide clicked")}
            />,
            <ButtonSm
              key="Ask Question on Discord"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="Ask Question on Discord"
              iconClass="discord-icon"
              onClick={() => console.log("Ask Question on Discord clicked")}
            />,
            <ButtonSm
              key="Download Sample Videos"
              buttonType="full-width"
              text="Download Sample Videos"
              iconClass="download-icon"
              onClick={() => console.log("Download Sample Videos clicked")}
            />,
          ]}
        />
      </div>
    </div>
  );
};

export default HeaderPanel;
