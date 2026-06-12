import React from 'react';

const NUM_TILES = 6;

const CameraEmptyState: React.FC = () => {
  return (
    <div className="video-container flex flex-row flex-wrap gap-2 flex-1 flex-start mt-1">
      {Array.from({ length: NUM_TILES }).map((_, index) => (
        <div
          key={index}
          className={`flex p-1 gap-1 flex-col video-tile camera-source br-2 pos-rel size-3 bg-middark empty video-tile-${index}`}
        >
          <div className="video-feed-container overflow-hidden br-1">
            <div className="flex w-full h-full items-center justify-center text-gray-400 text-sm">
              {/* Optional placeholder text or icon can go here */}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default CameraEmptyState;