export const download = (inputBlob: Blob, outputFileName: string) => {
  const url = URL.createObjectURL(inputBlob);
  const a = document.createElement("a");
  a.style.display = "none"; // Proper way to set the style
  a.href = url;
  a.download = outputFileName;
  document.body.appendChild(a); // Append after setting properties to avoid reflow
  a.click();
  document.body.removeChild(a); // Clean up the DOM
  window.URL.revokeObjectURL(url); // Clean up the URL
}
