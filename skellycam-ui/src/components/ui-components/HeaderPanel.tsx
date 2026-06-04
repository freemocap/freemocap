import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import ButtonSm from "./ButtonSm";
import DropdownButton from "./DropdownButton";
import { SettingsModal } from "./SettingsModal";
import { EXTERNAL_URLS } from "@/constants/external-urls";

export default function HeaderPanel() {
  const { t } = useTranslation();
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <div className="header-panel flex flex-row justify-content-space-between top-header br-2 h-25">
        <div className="flex right-section gap-2 items-center">
          <ButtonSm
            iconClass="settings-icon"
            text={t('settings')}
            textColor="text-gray"
            onClick={() => setSettingsOpen(true)}
          />

          <ButtonSm
            iconClass="donate-icon"
            text="Support FreeMoCap"
            rightSideIcon="externallink"
            textColor="text-gray"
            onClick={() => window.open(EXTERNAL_URLS.DONATE, "_blank")}
          />

          <DropdownButton
            containerClassName="align-end"
            buttonProps={{
              text: "Help",
              rightSideIcon: "dropdown",
              textColor: "text-gray",
              iconClass: ""
            }}
            dropdownItems={[
              <ButtonSm
                key="Skellycam Documentation"
                rightSideIcon="externallink"
                buttonType="full-width"
                text="Skellycam Documentation"
                iconClass="learn-icon"
                onClick={() => window.open(EXTERNAL_URLS.DOCS_INTRO, "_blank")}
              />,
              <ButtonSm
                key="Ask Question on Discord"
                rightSideIcon="externallink"
                buttonType="full-width"
                text="Ask Question on Discord"
                iconClass="discord-icon"
                onClick={() => window.open(EXTERNAL_URLS.DISCORD, "_blank")}
              />,
            ]}
          />
        </div>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
