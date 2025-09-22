import {type FC, type MouseEvent, type ReactElement} from "react";
import {ConnectionDropdown} from "@/components/features/ConnectionDropdown/ConnectionDropdown.tsx";
import {ButtonSm} from "@/components/primitives/Buttons/ButtonSm.tsx";
import DropdownButton from "@/components/composites/DropdownButton.tsx";

export interface HeaderProps {
    onSupportClick?: () => void;
    onHelpItemClick?: (item: string) => void;
}

export const Header: FC<HeaderProps> = (): ReactElement => {
    const handleSupportClick = (event: MouseEvent<HTMLButtonElement>): void => {
        event.preventDefault();
            console.log("Support freemocap clicked");
            // TODO: Add navigation to donation/support page
    };

    const handleHelpItemClick = (item: string): void => {
            console.log(`${item} clicked`);
            // TODO: Add navigation logic based on item
    };

    const helpDropdownItems: ReactElement[] = [
        <ButtonSm
            key="FreeMocap Guide"
            rightSideIcon="externallink"
            buttonType="full-width"
            text="FreeMocap Guide"
            iconClass="learn-icon"
            onClick={() => handleHelpItemClick("FreeMocap Guide")}
        />,
        <ButtonSm
            key="Ask Question on Discord"
            rightSideIcon="externallink"
            buttonType="full-width"
            text="Ask Question on Discord"
            iconClass="discord-icon"
            onClick={() => handleHelpItemClick("Ask Question on Discord")}
        />,
        <ButtonSm
            key="tutorials"
            buttonType="full-width"
            text="Download Sample Videos"
            iconClass="download-icon"
            onClick={() => handleHelpItemClick("Download Sample Videos")}
        />,
    ];

    return (
        <div className="flex flex-row justify-content-space-between top-header br-2 h-25">
            <div className="flex left-section">
                <ConnectionDropdown/>
            </div>
            <div className="flex right-section gap-2">
                <ButtonSm
                    iconClass="donate-icon"
                    text="Support freemocap"
                    rightSideIcon="externallink"
                    textColor="text-gray"
                    onClick={handleSupportClick}
                />

                <DropdownButton
                    containerClassName="align-end"
                    buttonProps={{
                        text: "Help",
                        rightSideIcon: "dropdown",
                        textColor: "text-gray",
                        iconClass: "",
                        onClick: () => console.log("help dropdown button clicked"),
                    }}
                    dropdownItems={helpDropdownItems}
                />
            </div>
        </div>
    );
};
