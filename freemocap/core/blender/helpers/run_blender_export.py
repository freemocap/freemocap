import json
import sys
import traceback


def _fix_io_addons_on_python_314():
    """Work around Blender builds running on Python >= 3.14 (e.g. Ubuntu's distro Blender).

    `bpy_extras.io_utils.orientation_helper` checks `"__annotations__" not in cls.__dict__`,
    which is always true under PEP 649 lazy annotations, so it replaces the class's
    annotations with an empty dict. The FBX/BVH exporters then register with only their
    axis properties and calls like `export_scene.fbx(use_selection=True)` fail with
    'keyword "use_selection" unrecognized'. Patch the decorator to merge the class's
    own annotations back in, then reload the affected core addons so they re-register.
    """
    if sys.version_info < (3, 14):
        return

    import inspect

    import addon_utils
    from bpy_extras import io_utils

    original_orientation_helper = io_utils.orientation_helper
    if getattr(original_orientation_helper, "_freemocap_patched", False):
        return

    def orientation_helper(*args, **kwargs):
        original_wrapper = original_orientation_helper(*args, **kwargs)

        def wrapper(cls):
            own_annotations = dict(inspect.get_annotations(cls))
            cls = original_wrapper(cls)
            # The original wrapper reset the annotations to just the axis properties
            cls.__annotations__ = {**own_annotations, **cls.__annotations__}
            return cls

        return wrapper

    orientation_helper._freemocap_patched = True
    io_utils.orientation_helper = orientation_helper

    for addon_name in ("io_scene_fbx", "io_anim_bvh"):
        if not addon_utils.check(addon_name)[1]:
            continue
        addon_utils.disable(addon_name, default_set=False)
        for mod_name in [m for m in list(sys.modules) if m == addon_name or m.startswith(addon_name + ".")]:
            del sys.modules[mod_name]
        addon_utils.enable(addon_name, default_set=False)
        print(f"Re-registered {addon_name} with Python 3.14 orientation_helper fix")


def run_blender_export(site_packages_path: str,
                       recording_path_input: str,
                       blender_file_save_path_input: str,
                       blender_export_config_input: dict | None = None):
    # Inject the freemocap venv's site-packages so freemocap_blender_addon is importable
    # without needing to install the addon into Blender. Append rather than prepend:
    # Blender's Python version can differ from the venv's (e.g. distro Blender on 3.14
    # vs a 3.12 venv), so compiled packages like numpy must come from Blender's own
    # paths - the venv's builds would fail with "No module named 'numpy._core._multiarray_umath'".
    if site_packages_path not in sys.path:
        sys.path.append(site_packages_path)

    # Blender's addons directory may contain a stale/broken `freemocap_blender_addon`
    # that Blender preloads as a namespace package, hijacking the name and causing
    # `from freemocap_blender_addon.main import ...` to fail silently. Evict any
    # preloaded copy and strip the addons path so our venv copy wins the import.
    for mod_name in [m for m in list(sys.modules) if m == "freemocap_blender_addon" or m.startswith("freemocap_blender_addon.")]:
        print(f"Evicting preloaded module from sys.modules: {mod_name}")
        del sys.modules[mod_name]
    sys.path[:] = [p for p in sys.path if "Blender Foundation" not in p or "addons" not in p.replace("\\", "/")]

    _fix_io_addons_on_python_314()

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
