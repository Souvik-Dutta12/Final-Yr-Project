import numpy as np

def apply_scl_mask(band, scl):
    masked = band.copy()
    masked[scl != 5] = 0
    return masked