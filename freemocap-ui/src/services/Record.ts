export interface Chunk {
  frameData: Blob,
  timestamp: number,
}

export class Record {
  public static recordStream = (recordedChunks: [Chunk]) => {
    return (e) => {
      if (e.data.size > 0) {
        recordedChunks.push({
          frameData: e.data,
          timestamp: Date.now()
        } as Chunk);
        console.log(recordedChunks)
      }
    }
  }
}

