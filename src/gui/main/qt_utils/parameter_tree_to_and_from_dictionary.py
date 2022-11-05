from typing import Dict, Any

from pyqtgraph.parametertree import Parameter


def create_parameter_tree_from_dictionary(
    dictionary: Dict[str, Any], name: str = "Root"
) -> Parameter:
    """
    Creates a ParameterTree from a dictionary.
    """
    parameter_tree = Parameter.create(name=name, type="group", children=[])
    for key, value in dictionary.items():
        if isinstance(value, dict):
            parameter_tree.addChild(create_parameter_tree_from_dictionary(value, key))
        else:
            parameter_tree.addChild(Parameter.create(name=key, type="str", value=value))
    return parameter_tree


def create_dictionary_from_parameter_tree(parameter_tree: Parameter) -> Dict[str, Any]:
    """
    Creates a dictionary from a ParameterTree.
    """
    dictionary = {}
    for child in parameter_tree.children():
        if isinstance(child, Parameter):
            dictionary[child.name()] = child.value()
        else:
            dictionary[child.name()] = create_dictionary_from_parameter_tree(child)
    return dictionary


if __name__ == "__main__":
    import pyqtgraph as pg
    from rich import print

    dict_to_tree = {
        "a": 1,
        "b": 2,
        "c": {"d": 3, "e": 4},
    }

    tree = create_parameter_tree_from_dictionary(dict_to_tree)

    dict_from_tree = create_dictionary_from_parameter_tree(tree)
    print(dict_from_tree)
    tree.show()

    app = pg.mkQApp()
    pg.exec()
