from pathlib import Path
from typing import Union

import sass


def compile_scss_to_css(scss_path: Union[str, Path], css_path: Union[str, Path]):
    with open(scss_path) as scss_file:
        scss_contents = scss_file.read()

    compiled_css = sass.compile(string=scss_contents)

    with open(css_path, "w") as css_file:
        css_file.write(compiled_css)
