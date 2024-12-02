from pathlib import Path
from typing import Optional

import laspy
import numpy as np
import open3d as o3d


DEFAULT_CLASS_LABEL = -100


class PointCloud:
    def __init__(
        self,
        xyz: Optional[np.ndarray] = None,
        rgb: Optional[np.ndarray] = None,
        offset: Optional[np.ndarray] = None,
        default_color: Optional[np.ndarray] = None,
        voxel_size: Optional[float] = None,
    ):
        self._xyz = xyz
        self._rgb = rgb
        self._offset = offset
        self._geometry = None
        self.label = DEFAULT_CLASS_LABEL
        self.default_color = default_color
        self.voxel_size = voxel_size
        self.is_voxelized = False
    
    def voxelize(self) -> None:
        xyz_voxelized = np.round((self._xyz - self._xyz.min(axis=0)) / self.voxel_size).astype(np.int32)
        _, idx = np.unique(xyz_voxelized, return_index=True, axis=0)
        self._xyz = self._xyz[idx]
        if self._rgb is not None:
            self._rgb = self._rgb[idx]
        self.is_voxelized = True
    
    def _make_geometry(self) -> None:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(self.xyz)
        pcd.colors = o3d.utility.Vector3dVector(self.rgb)
        self._geometry = pcd
    
    def clear(self) -> None:
        self._xyz = None
        self._rgb = None
        self._geometry = None

    @property
    def xyz(self) -> np.ndarray:
        if self.voxel_size is not None and not self.is_voxelized:
            self.voxelize()
        return self._xyz - self.offset

    @property
    def rgb(self) -> np.ndarray:
        assert self.xyz is not None
        if self._rgb is None or self.default_color is not None:
            return np.ones_like(self.xyz) * self.default_color
        return self._rgb

    @property
    def geometry(self) -> o3d.geometry.PointCloud:
        if self._geometry is None:
            self._make_geometry()
        return self._geometry
    
    @property
    def offset(self) -> np.ndarray:
        if self._offset is None:
            return np.array([[0, 0, 0]], dtype=np.float64)
        return self._offset 
    
    @offset.setter
    def offset(self, value: np.ndarray) -> None:
        self._offset = value
    
    @property
    def id(self) -> str:
        raise NotImplementedError
    
    @property
    def centroid_xy(self) -> tuple[float, float]:
        assert self.xyz is not None
        return tuple(self._xyz[:, :2].mean(axis=0))


class FilePointCloud(PointCloud):
    def __init__(self, path: Path, root: Path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.root = root
        self.relpath = path.relative_to(root)

    def _read_las(self) -> None:
        las = laspy.read(self.path)
        self._xyz = las.xyz
        self._rgb = None
        if hasattr(las, 'red'):
            self._rgb = (
                np.concatenate(
                    [
                        las.red[..., np.newaxis],
                        las.green[..., np.newaxis],
                        las.blue[..., np.newaxis],
                    ],
                    axis=1,
                ).astype(np.float64)
                / 2**16
            )

    @property
    def xyz(self) -> np.ndarray:
        if self._xyz is None:
            self._read_las()
        return super().xyz
    
    @property
    def id(self) -> str:
        return str(self.relpath)
    
    def __repr__(self) -> str:
        return f'FilePointCloud({self.relpath})'


class SlicePointCloud(PointCloud):
    def __init__(self, mask: np.ndarray, parent: PointCloud, **kwargs):
        super().__init__(**kwargs)
        self._parent = parent
        self._mask = mask

    @property
    def xyz(self) -> np.ndarray:
        if self._xyz is None:
            self._xyz = self._parent.xyz[self.mask]
        return super().xyz 

    def rgb(self) -> np.ndarray:
        if self._rgb is None:
            assert self._parent.rgb is not None
            self._rgb = self._parent.rgb[self._mask]
        return super().rgb
