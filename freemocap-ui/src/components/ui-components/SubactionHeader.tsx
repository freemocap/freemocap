import React from "react";

interface SubactionHeaderProps {
  text?: string;
  className?: string;
}

const SubactionHeader: React.FC<SubactionHeaderProps> = ({
  text = "",
  className = "",
}) => {
  return (
    <div className="subaction-header-container gap-1 br-1 flex justify-between items-center h-25 p-1 text-nowrap min-w-0 w-full">
      <div className="text-container overflow-hidden flex items-center text-nowrap min-w-0 w-full">
        <p className={`${className} text-nowrap text-left bg-md text-darkgray min-w-0 w-full`}>
          {text}
        </p>
      </div>
    </div>
  );
};

export default SubactionHeader;