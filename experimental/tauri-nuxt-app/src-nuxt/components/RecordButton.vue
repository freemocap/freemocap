<!--<script setup lang="ts">-->
<!--import {ref} from "vue";-->
<!--import {createDir, Dir, writeFile} from "@tauri-apps/api/fs";-->

<!--const isRecording = ref(false);-->

<!--const startRecording = () => {-->
<!--  console.log("Starting recording");-->
<!--  cameraViews.value.forEach(-->
<!--      (cameraView, index) => {-->
<!--        const stream = cameraView.getStream();-->
<!--        const mediaRecorder = new MediaRecorder(stream);-->
<!--        mediaRecorders.value[index] = {-->
<!--          mediaRecorder,-->
<!--          recordedChunks: []-->
<!--        };-->

<!--        mediaRecorder.ondataavailable = (event) => {-->
<!--          if (event.data.size > 0) {-->
<!--            mediaRecorders.value[index].recordedChunks.push(event.data);-->
<!--          }-->
<!--        };-->
<!--        mediaRecorder.start()-->
<!--      });-->
<!--};-->


<!--const stopRecording = async () => {-->

<!--  // Create a promise for each mediaRecorder to stop and save its corresponding file.-->
<!--  const stopPromises = mediaRecorders.value.map(({ mediaRecorder, recordedChunks }, index) => {-->
<!--    return new Promise(async (resolve) => {-->
<!--      mediaRecorder.onstop = async () => {-->
<!--        const blob = new Blob(recordedChunks, { type: 'video/webm' });-->
<!--        const buffer = await blob.arrayBuffer();-->
<!--        const uint8Array = new Uint8Array(buffer);-->
<!--        const filename = `camera-${index + 1}-${new Date().toISOString().replace(":","_")}.webm`;-->
<!--        const saveDir = '.'; // Change this to your desired directory-->

<!--        await createDir(saveDir, { dir: Dir.Document, recursive: true });-->
<!--        await writeFile({-->
<!--          path: `${saveDir}/${filename}`,-->
<!--          contents: uint8Array-->
<!--        });-->

<!--        console.log(`Video saved to: ${saveDir}/${filename}`);-->
<!--        resolve(); // Resolve the promise once the file is saved.-->
<!--      };-->
<!--      mediaRecorder.stop(); // Stops the recording and triggers the onstop event.-->
<!--    });-->
<!--  });-->

<!--  // Wait for all media recorders to stop and save files.-->
<!--  await Promise.all(stopPromises);-->
<!--  isRecording.value = false; // Only toggle the state after all recordings have been stopped.-->
<!--};-->

<!--const toggleRecording = async () => {-->
<!--  if (isRecording.value) {-->
<!--    await stopRecording();-->
<!--  } else {-->
<!--    await startRecording();-->
<!--  }-->
<!--  isRecording.value = !isRecording.value;-->
<!--};-->

<!--</script>-->

<!--<template>-->
<!--  <button-->
<!--      class="record-button"-->
<!--      :class="{ 'recording': isRecording }"-->
<!--      @click="toggleRecording">{{ isRecording ? 'Stop' : 'Record' }}-->
<!--  </button>-->
<!--</template>-->

<!--<style scoped>-->
<!--.record-button {-->
<!--  position: fixed;-->
<!--  bottom: 20px;-->
<!--  right: 20px;-->
<!--  padding: 10px;-->
<!--  font-size: 16px;-->
<!--  background-color: #007bff;-->
<!--  border: 2px solid #0a21a9;-->
<!--  border-radius: 5px;-->
<!--  cursor: pointer;-->
<!--  transition: background-color 0.3s;-->
<!--}-->
<!--.record-button:hover {-->
<!--  background-color: #0056b3;-->
<!--}-->
<!--.record-button.recording {-->
<!--  background-color: #dc3545;-->
<!--  border-color: #8b0000;-->
<!--}-->
<!--</style>-->
