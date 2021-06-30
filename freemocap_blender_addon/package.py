"""Packages the addon and dependency"""
import importlib
import os
import re
import zipfile

import freemocap_blender_addon

ignored_directories = (
    '__pycache__',
    '.DS_Store'
)


def gather_files(basedir, arc_prefix=''):
    """Walk the given directory and return a sequence of filepath, archive name
    pairs.

    Args:
        basedir: The directory to start the walk

        arc_prefix: A path to join to the front of the relative (to basedir)
            file path

    Returns:
        A sequence of (filepath, archive name) pairs
    """
    results = []

    for path, subdirectories, files in os.walk(basedir):
        if os.path.basename(path) in ignored_directories:
            continue

        for file in files:
            relative_path = os.path.join(path, file)
            full_path = os.path.abspath(relative_path)
            arcname = os.path.relpath(full_path, os.path.dirname(basedir))
            arcname = os.path.join(arc_prefix, arcname)

            results.append((full_path, arcname))

    return results


def get_required_modules():
    """Parse the requirements.txt file to determine dependencies.

    Returns:
        A sequence of module names
    """
    with open('requirements.txt') as file:
        data = file.read()
        modules = data.split('\n')
        pattern = '([A-Za-z0-9]+)(?:[<=>]+.*\n)?'

        def get_module_name(s):
            result = re.search(pattern, s)

            if result:
                return result.group()

        modules = [get_module_name(s) for s in modules if s]

        return modules


def run():
    try:
        os.mkdir('dist')

    except FileExistsError:
        pass

    zip_entries = gather_files('freemocap_blender_addon')

    for module in get_required_modules():
        module = importlib.import_module(module)
        zip_entries += gather_files(os.path.dirname(module.__file__), os.path.join('freemocap_blender_addon', 'modules'))

    filename = f'freemocap_blender_addon-{freemocap_blender_addon.__version__}.zip'
    filepath = os.path.abspath(os.path.join('dist', filename))
    with zipfile.ZipFile(filepath, 'w') as dist_zip:
        for filename, arcname in zip_entries:
            dist_zip.write(filename, arcname)


if __name__ == '__main__':
    run()
