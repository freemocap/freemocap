import React from "react";

interface ButtonCardProps {
  text: string;
  iconClass: string;
  onClick: () => void;
  className?: string;
}

const ButtonCard: React.FC<ButtonCardProps> = ({ text, iconClass, onClick, className = "" }) => {
  return (
    <div
      className={`button items-center text-nowrap flex-col justify-content-space-between p-3 button card bg-dark flex-1 br-2 flex items-center justify-center text-white ${className}`}
      onClick={onClick}
    >
      <span className={`icon m-3 ${iconClass}`} />
      <p className="text-center text bg">{text}</p>
    </div>
  );
};

export default ButtonCard;
