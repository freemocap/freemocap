from pyfiglet import Figlet

def figlet(input_string, font_name='banner3'):
    """simple wrapper for pyfiglet, take in string and return in figlet ascii format (default font ('banner3')"""

    f = Figlet(font=font_name)

    return f.renderText(str(input_string))

if __name__== '__main__':
    import sys
    input_string = ''

    for thisArg in sys.argv[1:]:
        input_string = input_string + thisArg +' '

    if not input_string:
        input_string = 'henlo big txt'

    print(figlet(input_string))
