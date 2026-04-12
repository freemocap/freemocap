def get_numpy_path():
    # This is some screwy nonsense added to avoid numpy import weirdness in blender, is it still necessary?
    import numpy

    return numpy.__file__


if __name__ == "__main__":
    numpy_path = get_numpy_path()
    print(numpy_path)
