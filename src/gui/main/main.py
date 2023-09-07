import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(
        "User tried using `pre-alpha` entry point (`import freemocap: freemocap.RunMe() - displaying friendly message then re-directing to `freemocap.__main__:main()` entry point"
    )

    print(
        "--------------------------------\n"
        "--------------------------------\n"
        "--------------------------------\n"
        "Hello! Looks like you're trying to use the `alpha GUI` entry point for FreeMoCap.\n"
        "This entry point is deprecated, so we're launching the GUI via `freemocap.__main__:main()` entry point.\n"
        "If you want use the `alpha GUI` code, use check out the `v0.1.0` tag in the github repo.\n"
        "Thank you for using FreeMoCap!\n"
        "--------------------------------\n"
        "(NOTE  - this entry point will be removed eventually\n"
        "--------------------------------\n"
        "--------------------------------\n"
    )

    from freemocap.__main__ import main

    main()
