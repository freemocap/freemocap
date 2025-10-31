import React from "react";

interface SubactionHeaderProps {
  text?: string;
}

const SubactionHeader: React.FC<SubactionHeaderProps> = ({
  text = "2d image trackers",
}) => {
  return (
    <div className="subaction-header-container gap-1 br-1 flex justify-between items-center h-25 p-1">
      <div className="text-container overflow-hidden flex items-center">
        <p className="text-nowrap text-left bg-md text-darkgray">{text}</p>
      </div>
    </div>
  );
};

export default SubactionHeader;
