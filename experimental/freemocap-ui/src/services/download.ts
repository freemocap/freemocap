

export const download = (inputBlob: Blob, outputFileName) => {
  const url = URL.createObjectURL(inputBlob);
  const a = document.createElement("a");
  document.body.appendChild(a);
  // @ts-ignore
  a.style = "display: none";
  a.href = url;
  a.download = outputFileName;
  a.click();
  window.URL.revokeObjectURL(url);
}