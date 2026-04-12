import sys


def run_blender_export(site_packages_path: str, recording_path_input: str, blender_file_save_path_input: str):
    # Inject the freemocap venv's site-packages so freemocap_blender_addon is importable
    # without needing to install the addon into Blender
    if site_packages_path not in sys.path:
        sys.path.insert(0, site_packages_path)

    from freemocap_blender_addon.main import ajc27_run_as_main_function

    ajc27_run_as_main_function(recording_path=str(recording_path_input),
                               blend_file_path=str(blender_file_save_path_input))


if __name__ == "__main__":
    print(f"\nRunning {__file__} as a subprocess...\n")
    argv = sys.argv
    print(f"Received command line arguments: {argv}")
    argv = argv[argv.index("--") + 1:]
    site_packages_path_input = str(argv[0])
    recording_path_input = str(argv[1])
    blender_file_save_path_input = str(argv[2])
    run_blender_export(site_packages_path=site_packages_path_input,
                       recording_path_input=recording_path_input,
                       blender_file_save_path_input=blender_file_save_path_input)

    print("\nDone!\n")
