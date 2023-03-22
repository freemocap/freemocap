import sass
from pathlib import Path

def compile_scss_to_css():
    current_directory = Path(__file__).resolve().parent

    scss_filename = 'qt_style_sheet.scss'
    css_filename = 'qt_style_sheet.css'

    scss_path = current_directory / scss_filename
    css_path = current_directory / css_filename

    with open(scss_path) as scss_file:
        scss_contents = scss_file.read()

    compiled_css = sass.compile(string=scss_contents)

    with open(css_path, 'w') as css_file:
        css_file.write(compiled_css)

if __name__ == "__main__":
    compile_scss_to_css()
