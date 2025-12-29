import numpy as np

def normalize(img):
    img = img / 10000.0
    return np.clip(img, 0, 1)
