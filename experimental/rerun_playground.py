import rerun as rr
import numpy as np

rr.init("rerun_example_my_data", spawn=True)

positions = np.zeros((10, 3))
positions[:,0] = np.linspace(-10,10,10)

colors = np.zeros((10,3), dtype=np.uint8)
colors[:,0] = np.linspace(0,255,10)

rr.log(
    "my_points",
    rr.Points3D(positions, colors=colors, radii=0.5)
)
