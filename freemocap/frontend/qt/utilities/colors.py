import colorsys

import numpy as np


def bright_color_generator():
    hue = 0  # initialize hue

    while True:
        # create a bright color by using the full saturation and value
        # hue is varied over time to generate different colors
        r, g, b = [int(255 * i) for i in colorsys.hsv_to_rgb(hue, 1, 1)]

        yield r, g, b

        # increment hue
        hue += 0.1
        # avoid red and blue areas by wrapping back to 0.2 when it reaches 0.6
        if hue >= 0.6:  # hue wraps back to 0.2 when it reaches 0.6
            hue = 0.2


bright_colors = bright_color_generator()


def get_next_color():
    return next(bright_colors)


def rgb_color_generator(start_color, end_color, phase_increment=0.01):
    r_start, g_start, b_start = start_color
    r_end, g_end, b_end = end_color

    # Calculate the range of each color
    r_range = r_end - r_start
    g_range = g_end - g_start
    b_range = b_end - b_start

    # Initialize the current phase of each color wave
    r_phase = 0
    g_phase = np.pi / 3  # Offset the green phase by 1/3 of a wave
    b_phase = 2 * np.pi / 3  # Offset the blue phase by 2/3 of a wave

    while True:
        # Calculate the current color using a sinusoidal wave
        r = int(r_start + r_range * (np.sin(r_phase) + 1) / 2)
        g = int(g_start + g_range * (np.sin(g_phase) + 1) / 2)
        b = int(b_start + b_range * (np.sin(b_phase) + 1) / 2)

        yield r, g, b

        # Advance the phase of each color wave
        r_phase += phase_increment
        g_phase += phase_increment
        b_phase += phase_increment

        # Wrap the phase back to the start if it exceeds 2*pi
        if r_phase > 2 * np.pi:
            r_phase -= 2 * np.pi
        if g_phase > 2 * np.pi:
            g_phase -= 2 * np.pi
        if b_phase > 2 * np.pi:
            b_phase -= 2 * np.pi
