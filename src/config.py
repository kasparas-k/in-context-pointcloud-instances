from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from omegaconf import OmegaConf


@dataclass
class Style:
    point_size: float
    default_color: tuple[float, float, float]
    voxel_size: Optional[float] = None


@dataclass
class Data:
    pointcloud_root: Path
    background_pointcloud_root: Optional[Path] = None
    instance_id_field: Optional[str] = None
    in_json: Optional[Path] = None
    out_json: Optional[Path] = None
    projection: Optional[str] = None


class ColorMode(Enum):
    """
    Color rendering modes for foreground and background point clouds.
    RGB means the point cloud's original RGB values, DEF means the
    color values defined in viewer.foreground_style.default_color
    and viewer.background_style.default_color for foreground and
    background, respectively.

    RGB_RGB -- foreground and background original RGB
    DEF_RGB -- user-defined color for foreground, original RGB for
    background

    and so on.
    """
    RGB_RGB = 1
    DEF_RGB = 2
    DEF_DEF = 3
    RGB_DEF = 4


class Viewpoint(Enum):
    TOP = 1
    SIDE = 2


@dataclass
class Viewer:
    foreground_style: Style = Style(8, (0.75, 0.0, 0.0), None)
    background_style: Style = Style(5, (0.5, 0.5, 0.5), 0.2)
    viewpoint: Viewpoint = Viewpoint.TOP
    view_box: tuple[float, float, float] = (50.0, 50.0, 50.0)
    color_mode: ColorMode = ColorMode.RGB_RGB


@dataclass
class ClassificationKeymapping:
    q_class: str | int = 'bad' 
    w_class: str | int = 'multiple' 
    e_class: str | int = 'ok' 
    r_class: str | int = 'good'
    t_class: str | int = 'ignore'


@dataclass
class Labeling:
    """
    Config key to define labeling options and labeling-related behavior

    next_on_label: bool = True
        if True, proceed to the next point cloud once a label is added
        if False, stay on the current point cloud after adding a label
    classification_keymapping:
        string or integer label assignments to the q, w, e, r, t keys.
    """
    next_on_label: bool = True
    classification_keymapping: ClassificationKeymapping = ClassificationKeymapping()


@dataclass
class Config:
    data: Data
    viewer: Viewer = Viewer()
    labeling: Labeling = Labeling()


def get_config(config_path: Path) -> Config:
    default = OmegaConf.structured(Config)
    config = OmegaConf.load(config_path)
    config: Config = OmegaConf.merge(default, config)
    bg_root = config.data.background_pointcloud_root
    instance_id = config.data.instance_id_field
    assert (
        (instance_id is not None and bg_root is None)
        or (instance_id is None and bg_root is not None)
        or (instance_id is None and bg_root is None)
    ), 'Cannot set background pc root and foreground pc instance field name at once'
    return config
