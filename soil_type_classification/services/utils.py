import numpy as np
import torch

def compute_class_weights(labels):
    counts = np.bincount(labels)
    weights = 1. / (counts + 1e-6)
    weights = weights / weights.sum()
    return torch.tensor(weights, dtype=torch.float32)