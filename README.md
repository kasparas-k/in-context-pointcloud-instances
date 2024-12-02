# in-context-pointcloud-instances

A minimal point cloud viewer for visually inspecting automatically extracted object instances in-context, and assigning user-defined labels, based on [Open3D](https://github.com/isl-org/Open3D).

## Intended use case

This viewer was originally developed for labeling automatically extracted object instances as "correct" and "incorrect":

1. (Before using this tool) extract individual object point clouds from a larger point cloud (example: extract individual trees from a city point cloud and save them as separate files)
2. Check the extracted point clouds in the context of their parent point cloud for correctness
3. If the point cloud has geographical coordinates, open Google Maps and check the object on Google Street View
4. Label the extracted object based on its segmentation correctness

The labels can be defined to be anything, so if you have a good instance extraction  result without semantic labels, you can use this tool to add semantic labels to all individual point clouds.

## Installation

This program was developed and tested for Python 3.12, but should work with Python versions 3.10 and newer.

```bash
pip install -r requirements.txt
```

## How to use

Edit your config file, then run

```bash
python app.py <PATH_TO_CONFIG_YAML>
```

Keyboard controls:
| Key     | Action                                |
|---------|----------------------------------------|
| `a`     | Previous point cloud                   |
| `d`     | Next point cloud                       |
| `m`     | Open map at current object center      |
| `q`     | Assign first class                     |
| `w`     | Assign second class                    |
| `e`     | Assign third class                     |
| `r`     | Assign fourth class                    |
| `t`     | Assign fifth class                     |

The required dataset structure and config are detailed below:

### Input data structure

#### a) Individual object point clouds only
If you're not using background point clouds (parent point cloud of the extracted objects), any foreground point cloud directory `pointcloud_root` that contains `*.las` and `*.laz` files is appropriate.

#### b) Individual object point clouds and background (parent) point clouds
If you want to view individual object point clouds in the context of their parent point cloud, the two directories `pointcloud_root` (foreground point clouds) and `background_pointcloud_root` need to have matching subdirectory structures:

`background_pointcloud_root` contains the parent point clouds from which individual objects were extracted. 
```
my_parent_point_clouds
├── subdir_1
│   ├── city.laz
│   └── park.laz
└── subdir_2
    └── ...
```

`pointcloud_root` has the exact same subdirectory structure, but an additional directory named after its parent point cloud that contains all individual objects extracted from it. Names of individual object point clouds do not matter, as long as they are placed in the correct subdirectory.

```
my_foreground_objects
├── subdir_1
│   ├── city
│   │   ├── 01.laz
│   │   ├── 02.laz
│   │   ├── ...
│   │   └── n.laz
│   └── park
│       ├── any_name.laz
│       ├── ...
│       └── las_or_laz.las
└── subdir_2
    └── ...
```

#### c) [TODO] Full point cloud with object instance labels

Not yet implemented. A las/laz file with a specified object instance ID field could be used by itself to generate both foregrounds and backgrounds. 

### Config

The config consists of three main parts: `data`, `viewer` and `labeling`.


The `data` key describes the input data, labels as well as the outputs.
```yaml
data:
    # directory containing main (foreground) point clouds
    pointcloud_root: /data/pointcloud/extracted

    # ===========================================
    # === THE FOLLOWING KEYS ARE ALL OPTIONAL ===
    # ===========================================
    
    # directory containing the parent point clouds of the above-mentioned pointcloud_root
    # if not specified, only foregrounds will be viewed.
    background_pointcloud_root: /data/pointcloud/original
    
    # if an input json is specified, labels will be loaded
    # use this to continue your work (previous out_json) or to fix classification algorithm outputs
    in_json: /data/pointcloud/my_previous_work_session.json

    # if specified, save labels in a json file. if you just want to look at the point clouds,
    # you don't need to save the result. However, to prevent accidental
    # loss of work, every session's labels are saved in tmp/unnamed_label.json
    out_json: /data/pointcloud/final_labels_final_2_lastversion_myfinal.json

    # Coordinate Reference System of the point cloud. Used to open Google Maps at the object's location.
    projection: EPSG:3346
```

The `labeling` key describes the labeling scheme and the program's behavior when labeling:

```yaml
labeling:
    # if True, proceed to the next point cloud once a label is assigned
    # if False, stay on the current point cloud after a label is assigned
    # default: True
    next_on_label: True

    # string or integer class labels assigned to up to five keys
    # chosen from q, w, e, r, t
    classification_keymapping:
        q_class: 'bad'
        w_class: 'ok'
        e_class: 'good'
```

The `viewer` key describes the appearance of point clouds such as point size, color:
```yaml
viewer:
    # appearance of foreground point clouds, optional.
    # default configuration:
    foreground_style:
        # size of points in the viewer
        point_size: 8
        # (0, 1) normalized RGB values
        # this color is used when color_mode starts with DEF_*
        default_color: [0.75, 0.0, 0.0]  # red

    # same as foreground_style
    # default configuration:
    background_style:
        point_size: 5
        # this color is used when color_mode ends with *_DEF
        default_color: [0.5, 0.5, 0.5]  # grey
        # if provided, the point cloud will be voxelized using the given voxel size
        voxel_size: 0.2

    # One of the two initial viewpoints: TOP or SIDE
    # default: TOP
    viewpoint: TOP

    # x y and z size of the view box, which is used to crop the displayed point clouds
    # default: 50, 50, 50
    view_box: [50, 50, 50]

    # RGB means the point cloud's original RGB values, DEF means the
    # color values defined in viewer.foreground_style.default_color
    # and viewer.background_style.default_color for foreground and
    # background, respectively.
    # RGB_RGB -- foreground and background original RGB
    # DEF_RGB -- user-defined color for foreground, original RGB for
    # background, and so on.
    color_mode: DEF_RGB
```

### Continuing your work / using pre-generated labels

To continue your work, provide the path to your previous `data.out_json` file as the `data.in_json` config key. **The tool automatically skips to the first label that isn't `-100` to continue work, so do not use `-100` as part of your labeling scheme.**

To use pre-generated labels, create a json file with the following format:

```json
{
    "pointcloud/relative/path_0.laz": "my_label",
    ...
    "pointcloud/relative/path_n.laz": "my_label"
}
```

where the relative paths must be relative to `pointcloud_root`.

## Extending the functionality

Right now the tool supports a maximum of five classes, which can be bound to the keys q, w, e, r, t.
If you need more classes, refer to `ClassificationKeymapping` in [`src/config.py`](src/config.py) and 'SimplePointCloudApp._on_key' in [`app.py`](app.py).

A more flexible solution is also possible by using `getattr` on `gui.KeyName`, which is left as a low priority TODO for this repository.