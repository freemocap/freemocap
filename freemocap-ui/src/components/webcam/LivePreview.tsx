import React from "react";

interface Props {
  stream: MediaStream
}

export function LiveStreamPreview({ stream }) {
  let videoPreviewRef = React.useRef<HTMLVideoElement>();

  React.useEffect(() => {
    if (videoPreviewRef.current && stream) {
      // @ts-ignore
      videoPreviewRef.current.srcObject = stream;
    }
  }, [stream]);

  if (!stream) {
    return null;
  }

  // @ts-ignore
  return <video ref={videoPreviewRef} width={800} height={600} autoPlay />;
}
