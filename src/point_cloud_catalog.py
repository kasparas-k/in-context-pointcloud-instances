from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

import numpy as np

from .point_cloud import PointCloud


@dataclass
class PointcloudPair:
    fg: PointCloud
    center: np.ndarray
    bg: Optional[PointCloud] = None


class PointCloudGroup:
    def __init__(
        self,
        fg: list[PointCloud],
        bg: Optional[list[PointCloud]] = None,
    ):
        self.fg = fg
        if bg is not None:
            assert len(bg) == 1, 'Only one background point cloud per root is allowed'
            self.bg = bg[0]
        else:
            self.bg = None
        self.current_idx = -1
        self.offsets_set = False

    def __len__(self) -> int:
        return len(self.fg)

    def _set_offsets(self) -> None:
        offset = None
        if self.bg is not None:
            offset = np.min(self.bg.xyz, axis=0)
            self.bg.offset = offset
        for fg in self.fg:
            if offset is None:
                fg.offset = np.min(fg.xyz, axis=0)
            else:
                fg.offset = offset

    def next(self) -> PointcloudPair:
        self.current_idx = min(self.current_idx + 1, len(self))
        return self.get_pointcloud_pair()

    def prev(self) -> PointcloudPair:
        self.current_idx = max(self.current_idx - 1, 0)
        return self.get_pointcloud_pair()

    def get_pointcloud_pair(self) -> PointcloudPair:
        if not self.offsets_set:
            self._set_offsets()
            self.offsets_set = True
        return PointcloudPair(
            fg=self.fg[self.current_idx],
            bg=self.bg,
            center=self.get_center(),
        )

    def clear(self) -> None:
        if self.bg is not None:
            self.bg.clear()
        for fg in self.fg:
            fg.clear()

    def reached_end(self) -> bool:
        if self.current_idx == len(self) - 1:
            self.current_idx = len(self)
            return True
        return False

    def reached_start(self) -> bool:
        if self.current_idx == 0:
            self.current_idx = -1
            return True
        return False

    def get_center(self) -> np.ndarray:
        return np.array([*np.mean(self.fg[self.current_idx].xyz[:, :2], axis=0), 0])


class PointCloudCatalog:
    def __init__(
        self,
        root_to_pcs: dict,
    ):
        self.groups: list[PointCloudGroup] = []
        for root, pcs in root_to_pcs.items():
            self.groups.append(
                PointCloudGroup(pcs['fg'], pcs.get('bg'))
            )
        self.current_idx = 0
        self.id_to_fg = {fg.id: fg for group in self.groups for fg in group.fg}
        
        self.total_len = sum([len(g) for g in self.groups])
        self._total_pos = 0

    def __len__(self) -> int:
        return len(self.groups)

    def next(self) -> PointcloudPair:
        self._total_pos = min(self.total_len, self._total_pos + 1)
        if self.groups[self.current_idx].reached_end():
            self.groups[self.current_idx].clear()
            self.current_idx = min(self.current_idx + 1, len(self) - 1)
        return self.groups[self.current_idx].next()

    def prev(self) -> PointcloudPair:
        self._total_pos = max(0, self._total_pos - 1)
        if self.groups[self.current_idx].reached_start():
            self.groups[self.current_idx].clear()
            self.current_idx = max(self.current_idx - 1, 0)
        return self.groups[self.current_idx].prev()

    def load_label(self, json_path: Path) -> None:
        with open(json_path) as f:
            classes = json.load(f)
        for fg_id, label in classes.items():
            self.id_to_fg[fg_id].label = label

    def save_label(self, json_path: Path) -> None:
        labels = {fg_id: fg.label for fg_id, fg in self.id_to_fg.items()}
        json_path.parent.mkdir(exist_ok=True, parents=True)
        with open(json_path, 'w') as f:
            json.dump(labels, f)

    @property
    def current_pos(self) -> int:
        return self.groups[self.current_idx].current_idx + 1

    @property
    def total_pos(self) -> int:
        return self._total_pos

    @property
    def current_len(self) -> int:
        return len(self.groups[self.current_idx])

    def flip_to_first_label_occurrence(self, label: str | int = 1) -> None:
        total = 0
        broken = False
        for group_idx, group in enumerate(self.groups):
            for fg_idx, fg in enumerate(group.fg):
                total += 1
                if fg.label == label:
                    broken = True
                    break
            if broken:
                break
        
        self._total_pos = total - 1
        for g in self.groups[:group_idx]:
            g.current_idx = len(g) - 1
        
        if fg_idx > 0:
            self.current_idx = group_idx
            self.groups[self.current_idx].current_idx = fg_idx - 1
        else:
            self.current_idx = group_idx - 1
