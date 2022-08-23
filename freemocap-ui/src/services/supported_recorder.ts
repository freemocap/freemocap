export function supported() {
  console.log("Uncomment me to do useful stuff")
}
// function getSupportedMimeTypes(media, types, codecs) {
//   const isSupported = MediaRecorder.isTypeSupported;
//   const supported = [];
//   types.forEach((type) => {
//     const mimeType = `${media}/${type}`;
//     codecs.forEach((codec) => [
//         `${mimeType};codecs=${codec}`,
//         `${mimeType};codecs=${codec.toUpperCase()}`,
//         // /!\ false positive /!\
//         // `${mimeType};codecs:${codec}`,
//         // `${mimeType};codecs:${codec.toUpperCase()}`
//       ].forEach(variation => {
//         if(isSupported(variation))
//             supported.push_variables(variation);
//     }));
//     if (isSupported(mimeType))
//       supported.push_variables(mimeType);
//   });
//   return supported;
// };
//
// // Usage ------------------
//
// const videoTypes = ["webm", "ogg", "mp4", "x-matroska"];
// const audioTypes = ["webm", "ogg", "mp3", "x-matroska"];
// const codecs = ["should-not-be-supported","vp9", "vp9.0", "vp8", "vp8.0", "avc1", "av1", "h265", "h.265", "h264", "h.264", "opus", "pcm", "aac", "mpeg", "mp4a"];
//
// const supportedVideos = getSupportedMimeTypes("video", videoTypes, codecs);
// const supportedAudios = getSupportedMimeTypes("audio", audioTypes, codecs);
//
// console.log('-- Top supported Video : ', supportedVideos[0])
// console.log('-- Top supported Audio : ', supportedAudios[0])
// console.log('-- All supported Videos : ', supportedVideos)
// console.log('-- All supported Audios : ', supportedAudios)