import logging


def log_test_messages(logger: logging.Logger):
    logger.loop("This is a LOOP message, value `4` ->  For logs that are printed in a loop")
    logger.trace("This is a TRACE message, value `5` -> Low level logs for deep debugging")
    logger.debug("This is a DEBUG message, value `10` -> Detailed information for devs and curious folk")
    logger.info("This is an INFO message, value `20` -> General information about the program")
    logger.success("This is a SUCCESS message, value `22` ->  OMG, something worked!")
    logger.api("This is an IMPORTANT message, value `25` -> API calls/responses")
    logger.warning(
        "This is a WARNING message, value `30` -> Something unexpected happened, but it's necessarily an error"
    )
    logger.error("This is an ERROR message, value `40` -> Something went wrong!")

    print("----------This is a regular ol' print message.------------------")

    import time

    iters = 10
    for iter in range(1, iters + 1):
        wait_time = iter / 10
        logger.loop("Starting timers loop (Δt should probably be near 0, unless you've got other stuff going on)")
        tic = time.perf_counter_ns()
        time.sleep(wait_time)
        toc = time.perf_counter_ns()
        elapsed_time = (toc - tic) / 1e9
        logger.trace(f"Done {wait_time} sec timer - elapsed time:{elapsed_time}s (Δt should be ~{wait_time}s)")
