# __main__.py
import freemocap
from multiprocessing import freeze_support
from freemocap.icon_support import handle_icons


def main():
    # set up so you can change the taskbar icon - https://stackoverflow.com/a/74531530/14662833
    handle_icons()

    # run the freemocap gui
    freemocap.qt_gui_main()


if __name__ == "__main__":
    freeze_support()
    print(f"Running `freemocap.__main__` from - {__file__}")

    main()
