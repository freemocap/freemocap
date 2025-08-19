def get_numpy_path():
    import numpy

    return numpy.__file__


if __name__ == "__main__":
    numpy_path = get_numpy_path()
    print(numpy_path)
