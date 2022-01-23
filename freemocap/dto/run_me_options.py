from pydantic import BaseModel


class RunMeOptions(BaseModel):
    sessionID: str
    stage: int
    useOpenPose: bool = False
    runOpenPose: bool = True
    useMediaPipe: bool = True
    runMediaPipe: bool = True
    useDLC: bool = False
    dlcConfigPath: str
    debug: bool = False
    setDataPath: bool = False
    userDataPath: str = None
    recordVid: bool = True
    showAnimation: bool = True
    reconstructionConfidenceThreshold: float = .7
    # mm -
    # the size of the squares when printed on 8.5x11" paper based on parameters in ReadMe.md
    charucoSquareSize: int = 36
    calVideoFrameLength: float = .5
    startFrame: int = 0
    useBlender: bool = False
    resetBlenderExe: bool = False
