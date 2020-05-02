from random import choices

import numpy as np


def random_hex_string(length):
    return ''.join(choices('0123456789ABCDEF', k=length))


def count_distance(p1, p2):
    r12 = np.asarray(p1) - np.asarray(p2)
    return np.sqrt(r12.dot(r12))


def deserialize(spec):
    """Deserialize specification.

    :param spec:
    :return: model
    """
    if isinstance(spec, dict):
        model = spec['model']
        if isinstance(model, str):
            model = globals()[model]
        return model.deserialize(spec)
