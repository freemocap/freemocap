import logging
import traceback


class StringifyTracebackFilter(logging.Filter):
    """Converts live traceback objects in exc_info to pre-formatted strings.

    Some formatters (e.g. ColorFormatter) copy the LogRecord, which fails on
    live traceback objects since they can't be deepcopied or pickled. This
    filter runs before any handler sees the record: it formats the traceback
    into exc_text, then clears exc_info so nothing downstream chokes.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and record.exc_info[2] is not None:
            if not record.exc_text:
                record.exc_text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_info = None
        return True
