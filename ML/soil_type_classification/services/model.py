import h5py
import numpy as np
import torch
from torch.utils.data import Dataset
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models



class MultiH5Dataset(Dataset):

    def __init__(self, h5_files, split="train", transform=None):
        self.samples = []
        self.transform = transform

        split_map = {
            "train": 0,
            "val": 1,
            "test": 2
        }
        target_split = split_map[split]

        # Pre-index samples
        for file_path in h5_files:
            with h5py.File(file_path, "r") as f:
                splits = f["split"][:]  
                labels = f["labels"][:] 

                for i in range(len(labels)):
                    if splits[i] == target_split:
                        self.samples.append((file_path, i))


    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        file_path, i = self.samples[idx]

        with h5py.File(file_path, "r") as f:
            patch = f["patches"][i]
            index = f["indices"][i]
            label = f["labels"][i]
            

        # Combine → (10,256,256)
        x = np.concatenate([patch, index], axis=0)

        x = torch.tensor(x, dtype=torch.float32)
        y = torch.tensor(label, dtype=torch.long)

        # Apply augmentation
        if self.transform:
            x = self.transform(x)

        return x, y


class FocalLoss(nn.Module):
    """
    Handles class imbalance better than CrossEntropy
    """
    def __init__(self, alpha=None, gamma=2):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, weight=self.alpha, reduction='none')
        pt = torch.exp(-ce_loss)

        loss = ((1 - pt) ** self.gamma) * ce_loss
        return loss.mean()

# backbone
class Backbone(nn.Module):
    def __init__(self):
        super().__init__()

        m = models.resnet50(pretrained=True)

        # Change input channels 3 → 10
        m.conv1 = nn.Conv2d(10, 64, kernel_size=7, stride=2, padding=3, bias=False)

        self.stem = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool)
        self.layer1 = m.layer1
        self.layer2 = m.layer2
        self.layer3 = m.layer3
        self.layer4 = m.layer4

    def forward(self, x):
        x = self.stem(x)
        c2 = self.layer1(x)
        c3 = self.layer2(c2)
        c4 = self.layer3(c3)
        c5 = self.layer4(c4)

        return c2, c3, c4, c5


# fpn
class FPN(nn.Module):
    def __init__(self, out_channels=256):
        super().__init__()

        self.lateral = nn.ModuleList([
            nn.Conv2d(256, out_channels, 1),
            nn.Conv2d(512, out_channels, 1),
            nn.Conv2d(1024, out_channels, 1),
            nn.Conv2d(2048, out_channels, 1)
        ])

    def forward(self, features):
        c2, c3, c4, c5 = features

        p5 = self.lateral[3](c5)
        p4 = self.lateral[2](c4) + F.interpolate(p5, scale_factor=2)
        p3 = self.lateral[1](c3) + F.interpolate(p4, scale_factor=2)
        p2 = self.lateral[0](c2) + F.interpolate(p3, scale_factor=2)

        return p2


# transformer
class TransformerEncoder(nn.Module):
    def __init__(self, dim=256, heads=8, layers=4):
        super().__init__()

        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(d_model=dim, nhead=heads, batch_first=True)
            for _ in range(layers)
        ])

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return x

# full model
class HybridModel(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.backbone = Backbone()
        self.fpn = FPN()
        self.transformer = TransformerEncoder()

        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(256, num_classes)

    def forward(self, x):
        features = self.backbone(x)

        x = self.fpn(features)  # (B,256,H,W)

        B, C, H, W = x.shape

        # Flatten spatial → sequence
        x = x.view(B, C, H*W).permute(0, 2, 1)

        x = self.transformer(x)

        x = x.mean(dim=1)

        x = self.dropout(x)

        return self.fc(x)
