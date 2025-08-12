LOG_POINTER_STRING = "└>>"
LOG_FORMAT_STRING_WO_PID_TID = LOG_POINTER_STRING + (
    " %(message)s | "
    " %(levelname)s | "
    " %(delta_t)s | " 
    " %(name)s.%(funcName)s():%(lineno)s | "
    " %(asctime)s | "
)

LOG_FORMAT_STRING  = LOG_FORMAT_STRING_WO_PID_TID + (
    " PID:%(process)d:%(processName)s | "
    " TID:%(thread)d:%(threadName)s"
)

COLOR_LOG_FORMAT_STRING = LOG_FORMAT_STRING_WO_PID_TID + (
    " %(pid_color)sPID:%(process)d:%(processName)s\033[0m | "
    " %(tid_color)sTID:%(thread)d:%(threadName)s\033[0m"
)
