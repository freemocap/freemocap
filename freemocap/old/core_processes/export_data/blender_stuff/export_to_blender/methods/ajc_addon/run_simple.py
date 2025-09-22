import sys


def run_simple(recording_path_input: str, blender_file_save_path_input: str):
    from ajc27_freemocap_blender_addon.main import ajc27_run_as_main_function

    ajc27_run_as_main_function(recording_path=str(recording_path_input),
                               blend_file_path=str(blender_file_save_path_input))


if __name__ == "__main__":
    print(f"\nRunning {__file__} as a subprocess to install the addon...\n")
    argv = sys.argv
    print(f"Received command line arguments: {argv}")
    argv = argv[argv.index("--") + 1:]
    recording_path_input = str(argv[0])
    blender_file_save_path_input = str(argv[1])
    run_simple(recording_path_input=recording_path_input, blender_file_save_path_input=blender_file_save_path_input)

    print("\nDone!\n")
