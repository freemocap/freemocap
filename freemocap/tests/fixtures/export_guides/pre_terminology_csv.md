# Reading wide CSV tables

Run the example from this `csv` folder. Dynamic tables have one row per saved frame, beginning with
`frame_number` and `timestamp_s`. Remaining columns are `point.component`, for
example `body.nose.x` or `pelvis.qw`. Names can contain periods: the last period
separates the component in current scientific exports. Ordinary CSV quoting handles
commas and quotes; there is no URL decoding step.

Names follow the recorded order. Spatial CSV components use canonical XYZ or WXYZ order; combined segment-pose tables append quaternion components. Other components follow their declared order. Large tables can be split into
row or column parts: one part is not the complete channel. Use `frame_slice` and
`value_column_slice` in the parent export inventory to identify the parts. Join
column parts by frame_number and verify their timestamps; concatenate row parts
in frame order. Never concatenate unrelated camera or model tables.

Static fit tables contain one row of named values and no frame or timestamp columns.

An empty field means the source entry was absent; `NaN` means an explicitly missing
value. Polars preserves empty numeric fields as null and explicit `NaN` as NaN.
Inspect them with `is_null()` and `is_nan()` before converting to NumPy for plotting.
2D tables contain pixel x/y and dimensionless confidence; 3D position units are
in the parent inventory. See the parent README for provenance and coordinates.

```python
from pathlib import Path
import polars as pl
import matplotlib.pyplot as plt

path = next(Path('.').glob('*.3d_landmarks--*.csv'))  # choose your table explicitly
# Polars reads the UTF-8 byte-order mark used by the spreadsheet export.
csv_query = pl.scan_csv(path)
print(csv_query.collect_schema().names())
column = next(c for c in csv_query.collect_schema().names() if c.endswith('.x'))
table = csv_query.select(pl.col('timestamp_s').cast(pl.Float64),
                         pl.col(column).cast(pl.Float64)).collect()
plt.plot(table['timestamp_s'].to_numpy() - table['timestamp_s'][0], table[column].to_numpy())
plt.xlabel('Elapsed time (s)')
plt.ylabel('X position (recorded units; see export inventory)')
plt.title(column)
plt.show()
```

This plots one coordinate of one landmark, not the full skeleton. To inspect
missing values, use `table[column].is_null()` and `table[column].is_nan()`. Choose a different named column to
compare landmarks or coordinates. Do not plot confidence as if it were distance.
