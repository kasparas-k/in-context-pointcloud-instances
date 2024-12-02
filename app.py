from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d
import open3d.visualization.gui as gui

from src.point_cloud import FilePointCloud, SlicePointCloud, DEFAULT_CLASS_LABEL
from src.point_cloud_catalog import PointCloudCatalog, PointcloudPair
from src.config import get_config, Config, ColorMode, Viewpoint
from src.open_map import open_map


class SimplePointCloudApp:
    def __init__(self, config: Config):
        gui.Application.instance.initialize()

        self.window = gui.Application.instance.create_window(
            "Point Cloud Viewer", 1024, 768
        )
        self.window.set_on_layout(self._on_layout)

        self.viewpoint = config.viewer.viewpoint

        self.scene = gui.SceneWidget()
        self.scene.scene = o3d.visualization.rendering.Open3DScene(self.window.renderer)
        self.window.add_child(self.scene)

        self.window.set_on_key(self._on_key)

        self.key_to_label = {
            k.split("_")[0]: v
            for k, v in config.labeling.classification_keymapping.items()
        }
        class_guide = '\n'.join([f'{k}: {v}' for k, v in self.key_to_label.items()])
        self.label = gui.Label(class_guide)
        self.label.text_color = gui.Color(1.0, 1.0, 1.0)
        self.label.background_color = gui.Color(0.0, 0.0, 0.0, 0.5)
        self.window.add_child(self.label)

        self.fg_root = config.data.pointcloud_root
        self.bg_root = config.data.background_pointcloud_root

        self.root_to_pc = {}

        self.fg_material = o3d.visualization.rendering.MaterialRecord()
        self.fg_material.point_size = config.viewer.foreground_style.point_size
        self.bg_material = o3d.visualization.rendering.MaterialRecord()
        self.bg_material.point_size = config.viewer.background_style.point_size
        self.fg_voxel_size = config.viewer.foreground_style.voxel_size
        self.bg_voxel_size = config.viewer.background_style.voxel_size

        self.fg_color = np.array(config.viewer.foreground_style.default_color)
        self.bg_color = np.array(config.viewer.background_style.default_color)
        self.color_mode = config.viewer.color_mode

        self.fg_pc = None
        self.bg_pc = None
        self.fg_geometry = None
        self.bg_geometry = None

        x, y, z = config.viewer.view_box
        self.min_corner = np.array([-x / 2, -y / 2, 0])
        self.max_corner = np.array([x / 2, y / 2, z])

        self.instance_field = config.data.instance_id_field
        self.catalog = self.make_point_cloud_catalog()
        if config.data.in_json is not None:
            self.catalog.load_label(config.data.in_json)
            self.catalog.flip_to_first_label_occurrence(DEFAULT_CLASS_LABEL)
        self.out_json = config.data.out_json

        self.projection = config.data.projection

        self.update_pc(self.catalog.next())

        self.next_on_label = config.labeling.next_on_label
    
    def _set_initial_camera(self):
        if self.viewpoint == Viewpoint.SIDE: 
            bounds = self.scene.scene.bounding_box
            center = bounds.get_center()
            extent = bounds.get_extent()

            eye = center + [0, extent[1] * 20, 0]  # Position camera along +Y axis
            up = [0, 0, 1]
            self.scene.scene.camera.look_at(center, eye, up)

    def make_point_cloud_catalog(self) -> PointCloudCatalog:
        root_to_pc = defaultdict(lambda: defaultdict(list))
        fg_pointcloud_paths = sorted(self.fg_root.rglob('*.laz')) + sorted(
            self.fg_root.rglob('*.las')
        )

        match self.color_mode:
            case ColorMode.RGB_RGB:
                fg_color = None
                bg_color = None
            case ColorMode.RGB_DEF:
                fg_color = None
                bg_color = self.bg_color
            case ColorMode.DEF_RGB:
                fg_color = self.fg_color
                bg_color = None
            case ColorMode.DEF_DEF:
                fg_color = self.fg_color
                bg_color = self.bg_color
            case _:
                raise NotImplementedError(f'No such color mode {self.color_mode}')

        if self.bg_root is not None:
            bg_pointcloud_paths = sorted(self.bg_root.rglob('*.laz')) + sorted(
                self.bg_root.rglob('*.las')
            )
            for pc in fg_pointcloud_paths:
                root_to_pc[pc.relative_to(self.fg_root).parent]['fg'].append(
                    FilePointCloud(pc, self.fg_root, default_color=fg_color, voxel_size=self.fg_voxel_size)
                )
            for pc in bg_pointcloud_paths:
                root_to_pc[pc.relative_to(self.bg_root).parent / pc.stem]['bg'].append(
                    FilePointCloud(pc, self.bg_root, default_color=bg_color, voxel_size=self.bg_voxel_size)
                )
            del_roots = []
            for root, pcs in root_to_pc.items():
                if 'bg' not in pcs or 'fg' not in pcs:
                    del_roots.append(root)
            for root in del_roots:
                del root_to_pc[root]

        elif self.instance_field is not None:
            raise NotImplementedError
            bg_pointcloud_paths = fg_pointcloud_paths
            for pc in bg_pointcloud_paths:
                root_to_pc[pc.relative_to(self.bg_root).parent]['bg'].append(
                    FilePointCloud(pc, self.fg_root)
                )

        else:
            for pc in fg_pointcloud_paths:
                root_to_pc[pc.relative_to(self.fg_root).parent]['fg'].append(
                    FilePointCloud(pc, self.fg_root, default_color=fg_color, voxel_size=self.fg_voxel_size)
                )

        return PointCloudCatalog(root_to_pc)

    def next_pc(self):
        self.update_window_title('LOADING...')
        self.update_pc(self.catalog.next())

    def prev_pc(self):
        self.update_window_title('LOADING...')
        self.update_pc(self.catalog.prev())

    def update_pc(self, pcs: PointcloudPair):
        self.color_vectors = {}

        center = pcs.center
        bounds = o3d.geometry.AxisAlignedBoundingBox(
            self.min_corner + center, self.max_corner + center
        )
        self.fg_pc = pcs.fg
        self.bg_pc = pcs.bg
        self.fg_geometry = pcs.fg.geometry

        self.scene.scene.clear_geometry()
        self.scene.scene.add_geometry("fg", self.fg_geometry, self.fg_material)
        if self.bg_pc is not None:
            self.bg_geometry = pcs.bg.geometry.crop(bounds)
            self.scene.scene.add_geometry("bg", self.bg_geometry, self.bg_material)

        self.scene.setup_camera(60, bounds, bounds.get_center())
        self.update_window_title()
        self._set_initial_camera()

    def _on_layout(self, layout_context):
        r = self.window.content_rect
        preferred_size = self.label.calc_preferred_size(
            layout_context, gui.Widget.Constraints()
        )
        self.label.frame = gui.Rect(10, 10, preferred_size.width, preferred_size.height)
        self.scene.frame = r

    def set_fg_label(self, label: str | int) -> None:
        self.fg_pc.label = label
        if self.next_on_label:
            self.next_pc()
    
    def open_map(self) -> None:
        open_map(
            center_xy=self.fg_pc.centroid_xy,
            proj=self.projection,
        )

    def _on_key(self, event):
        if event.type == o3d.visualization.gui.KeyEvent.UP:
            return

        match event.key:
            case gui.KeyName.D:
                self.next_pc()
            case gui.KeyName.A:
                self.prev_pc()

            case gui.KeyName.Q:
                self.set_fg_label(self.key_to_label['q'])
            case gui.KeyName.W:
                self.set_fg_label(self.key_to_label['w'])
            case gui.KeyName.E:
                self.set_fg_label(self.key_to_label['e'])
            case gui.KeyName.R:
                self.set_fg_label(self.key_to_label['r'])
            case gui.KeyName.T:
                self.set_fg_label(self.key_to_label['t'])

            case gui.KeyName.C:
                pass
                
            case gui.KeyName.M:
                self.open_map()

    def save(self):
        if self.out_json is not None:
            self.catalog.save_label(self.out_json)
        else:
            default_out = Path('tmp/unnamed_label.json')
            print(f'Did not specify output json. Saving labels in {default_out}')
            self.catalog.save_label(default_out)

    def run(self):
        gui.Application.instance.run()

    def update_window_title(self, title: Optional[str] = None) -> None:
        if title is None:
            title = (
                f'class: {self.fg_pc.label}'
                + f' -- CURRENT SCENE: {self.catalog.current_pos}/{self.catalog.current_len}'
                + f' -- TOTAL: {self.catalog.total_pos}/{self.catalog.total_len}'
            )

        self.window.title = title


if __name__ == "__main__":
    config = get_config('config.yaml')
    app = SimplePointCloudApp(config)
    try:
        app.run()
    except Exception as e:
        raise e
    finally:
        app.save()
