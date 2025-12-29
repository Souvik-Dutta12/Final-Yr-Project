import numpy as np

def stack_bands(b04, b03, b02, b08):
    return np.stack([b04, b03, b02, b08], axis=-1)

def save_scene(path, scene_array):
    np.save(path, scene_array)
