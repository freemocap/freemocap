import json
import sys
import traceback


def run_blender_export(site_packages_path: str,
                       recording_path_input: str,
                       blender_file_save_path_input: str,
                       blender_export_config_input: dict | None = None):
    # Inject the freemocap venv's site-packages so freemocap_blender_addon is importable
    # without needing to install the addon into Blender
    if site_packages_path not in sys.path:
        sys.path.insert(0, site_packages_path)

    # Blender's addons directory may contain a stale/broken `freemocap_blender_addon`
    # that Blender preloads as a namespace package, hijacking the name and causing
    # `from freemocap_blender_addon.main import ...` to fail silently. Evict any
    # preloaded copy and strip the addons path so our venv copy wins the import.
    for mod_name in [m for m in list(sys.modules) if m == "freemocap_blender_addon" or m.startswith("freemocap_blender_addon.")]:
        print(f"Evicting preloaded module from sys.modules: {mod_name}")
        del sys.modules[mod_name]
    sys.path[:] = [p for p in sys.path if "Blender Foundation" not in p or "addons" not in p.replace("\\", "/")]

    print(f"sys.path[0:3] = {sys.path[0:3]}")
    from freemocap_blender_addon.main import ajc27_run_as_main_function
    print(f"Imported ajc27_run_as_main_function from: {ajc27_run_as_main_function.__module__}")

    import freemocap_blender_addon.data_models.parameter_models.load_parameters_config as addon_config

    # An older addon build (no dict loader, or options it does not recognize) must
    # not fail the export - degrade to its defaults instead.
    config = addon_config.load_default_parameters_config()
    if blender_export_config_input:
        load_from_dict = getattr(addon_config, "load_parameters_config_from_dict", None)
        if load_from_dict is None:
            print(f"Installed freemocap_blender_addon cannot apply {blender_export_config_input!r}; using addon defaults")
        else:
            try:
                config = load_from_dict(blender_export_config_input)
                print(f"Addon config: {config}")
            except Exception as e:
                print(f"Could not apply Blender export config {blender_export_config_input!r} ({e}); using addon defaults")

    ajc27_run_as_main_function(recording_path=str(recording_path_input),
                               blend_file_path=str(blender_file_save_path_input),
                               config=config)


if __name__ == "__main__":
    try:
        print(f"\nRunning {__file__} as a subprocess...\n", flush=True)
        argv = sys.argv
        print(f"Received command line arguments: {argv}", flush=True)
        argv = argv[argv.index("--") + 1:]
        site_packages_path_input = str(argv[0])
        recording_path_input = str(argv[1])
        blender_file_save_path_input = str(argv[2])
        blender_export_config_input = json.loads(argv[3]) if len(argv) > 3 else None
        run_blender_export(site_packages_path=site_packages_path_input,
                           recording_path_input=recording_path_input,
                           blender_file_save_path_input=blender_file_save_path_input,
                           blender_export_config_input=blender_export_config_input)

        print("\nDone!\n", flush=True)
    except Exception:
        print("\n!!! Blender export script FAILED with exception:\n", flush=True)
        traceback.print_exc()
        sys.stderr.flush()
        sys.exit(1)
