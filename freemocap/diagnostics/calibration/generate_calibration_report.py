from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from jinja2 import Template
from packaging.version import Version
from packaging.version import parse as vparse
from plotly.subplots import make_subplots

CURRENT_SENTINEL = Version("9999.0.0")
EXPECTED = 58.0
OS_ORDER = ["Windows", "macOS", "Linux"]


def safe_parse(ver: str) -> Version:
    """Parse semantic versions; return a giant sentinel for 'current'"""
    return CURRENT_SENTINEL if ver == "current" else vparse(ver)


def load_summary_data():
    summary_csv = Path("freemocap/diagnostics/diagnostic_data/calibration_diagnostics_summary.csv")

    print(f"Loading data from: {summary_csv}")
    df = pd.read_csv(summary_csv)

    # Standardize OS names - remove any whitespace and fix case
    df["os"] = df["os"].str.strip()

    # Add version_key for sorting
    df["version_key"] = df["version"].apply(safe_parse)

    # Calculate mean_error if not present
    if "mean_error" not in df.columns:
        df["mean_error"] = df["mean_distance"] - EXPECTED

    # Sort by OS and version
    df = df.sort_values(["os", "version_key"], ascending=[True, True])

    return df


def generate_figures(df):
    OS_COLORS = {
        "Windows": "rgb(0, 114, 178)",  # blue
        "macOS": "rgb(213, 94, 0)",  # vermilion
        "Linux": "rgb(0, 158, 115)",  # bluish green
    }
    # Figure 1 – All OS mean distance over all versions
    fig1 = go.Figure()

    print("\n=== FIGURE 1 DATA ===")

    for os_name in OS_ORDER:
        # Try exact match first
        os_df = df[df["os"] == os_name].sort_values("version_key")

        print(f"\n{os_name}: {len(os_df)} data points")

        if len(os_df) > 0:
            print(f"  Versions: {list(os_df['version'])}")
            print(f"  Values: {list(os_df['mean_distance'])}")

            fig1.add_scatter(
                x=os_df["version"],
                y=os_df["mean_distance"],
                mode="lines+markers",
                name=os_name,
                line=dict(width=2),
                marker=dict(size=8, color=OS_COLORS.get(os_name, "gray")),
            )

    fig1.add_hline(
        y=EXPECTED,
        line_dash="dash",
        line_color="black",
        annotation_text="Expected size",
        annotation_position="top right",
    )

    fig1.update_layout(
        title="Mean Charuco Square Size (mm) – all operating systems",
        yaxis_title="Square Size Estimate (mm)",
        xaxis_title="FreeMoCap Version",
        title_font=dict(size=20),
        xaxis_title_font=dict(size=22),
        yaxis_title_font=dict(size=20),
        xaxis_tickfont=dict(size=16),
        yaxis_tickfont=dict(size=18),
        height=500,
        showlegend=True,
        legend=dict(x=0.02, y=0.98, xanchor="left", yanchor="top"),
    )

    # Figure 2 – Per OS, post-1.6.0
    print("\n=== FIGURE 2 DATA ===")

    # Filter for versions >= 1.6.0 (including "current")
    post = df[(df["version_key"] >= vparse("1.6.0")) | (df["version"] == "current")]
    print(f"Post-1.6.0 data: {len(post)} rows")
    print(f"OS distribution: {post['os'].value_counts().to_dict()}")

    fig2 = make_subplots(rows=1, cols=3, shared_yaxes=True, subplot_titles=OS_ORDER, horizontal_spacing=0.1)

    for col, os_name in enumerate(OS_ORDER, start=1):
        # Get data for this OS and sort by version
        os_data = post[post["os"] == os_name].sort_values("version_key")

        print(f"\n{os_name} (subplot {col}): {len(os_data)} points")
        if len(os_data) > 0:
            print(f"  Versions: {list(os_data['version'])}")
            print(f"  Values: {list(os_data['mean_distance'])}")

        if len(os_data) > 0:
            # Add scatter plot with error bars
            fig2.add_scatter(
                x=os_data["version"],
                y=os_data["mean_distance"],
                error_y=dict(type="data", array=os_data["std_distance"], visible=True, width=4, thickness=2),
                mode="markers",
                marker=dict(size=10, color=OS_COLORS.get(os_name, "gray")),
                showlegend=False,
                row=1,
                col=col,
            )

            # Add value annotations
            for _, row in os_data.iterrows():
                fig2.add_annotation(
                    x=row["version"],
                    y=row["mean_distance"] + row["std_distance"] + 0.3,
                    text=f"{row['mean_distance']:.2f}±{row['std_distance']:.2f}",
                    showarrow=False,
                    yanchor="bottom",
                    row=1,
                    col=col,
                    font=dict(size=10),
                )

        # Add expected line
        fig2.add_hline(y=EXPECTED, line_dash="dash", line_color="black", row=1, col=col)

        # Update x-axis
        fig2.update_xaxes(tickfont=dict(size=14), title_font=dict(size=16), title_text="Version", row=1, col=col)

    # Update y-axis (only for first subplot)
    fig2.update_yaxes(
        tickfont=dict(size=14),
        title_font=dict(size=16),
        title_text="Square-size estimate (mm)",
        range=[EXPECTED - 3, EXPECTED + 3],
        row=1,
        col=1,
    )

    fig2.update_layout(title="Charuco Square Size Estimate – versions ≥ 1.6.0", title_font=dict(size=20), height=400)

    # Figure 3 – Mean error plot
    print("\n=== FIGURE 3 DATA ===")

    fig3 = go.Figure()

    for os_name in OS_ORDER:
        os_data = post[post["os"] == os_name].sort_values("version_key")

        print(f"\n{os_name}: {len(os_data)} points")
        if len(os_data) > 0:
            print(f"  Versions: {list(os_data['version'])}")
            print(f"  Errors: {list(os_data['mean_error'])}")

        if len(os_data) > 0:
            fig3.add_trace(
                go.Scatter(
                    x=os_data["version"],
                    y=os_data["mean_error"],
                    mode="lines+markers",
                    name=os_name,
                    line=dict(width=2),
                    marker=dict(size=8, color=OS_COLORS.get(os_name, "gray")),
                )
            )

    fig3.add_hline(y=0, line_dash="dot", line_color="gray", annotation_text="No error", annotation_position="top right")

    fig3.update_layout(
        title="Mean Error in Square Size Estimate (Post v1.6.0)",
        yaxis_title="Mean error (mm)",
        xaxis_title="FreeMoCap version",
        height=400,
        xaxis_title_font=dict(size=22),
        yaxis_title_font=dict(size=20),
        xaxis_tickfont=dict(size=16),
        yaxis_tickfont=dict(size=18),
        showlegend=True,
        legend=dict(x=0.02, y=0.98, xanchor="left", yanchor="top"),
    )
    fig3.update_yaxes(
        range=[-0.5, 0.5],
    )
    return fig1, fig2, fig3


def generate_summary_table(df):
    print("\n=== TABLE DATA ===")

    # Get the latest data for each OS (highest version_key)
    latest = df.sort_values("version_key", ascending=False).groupby("os").first().reset_index()

    print("Latest data per OS:")
    print(latest[["os", "version", "mean_distance", "std_distance", "mean_error"]].to_string())

    # Create ordered dataframe
    ordered_latest = pd.DataFrame()
    for os_name in OS_ORDER:
        os_row = latest[latest["os"] == os_name]
        if len(os_row) > 0:
            ordered_latest = pd.concat([ordered_latest, os_row])

    if len(ordered_latest) == 0:
        print("WARNING: No data for table!")
        ordered_latest = pd.DataFrame(
            {"os": OS_ORDER, "mean_distance": [0, 0, 0], "std_distance": [0, 0, 0], "mean_error": [0, 0, 0]}
        )

    table = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["OS", "Mean Square Size ± SD (mm)", "Mean Error (mm)"],
                    fill_color="lightgray",
                    align="center",
                    font=dict(size=18),
                ),
                cells=dict(
                    values=[
                        ordered_latest["os"],
                        [
                            f"{m:.2f} ± {s:.2f}"
                            for m, s in zip(ordered_latest["mean_distance"], ordered_latest["std_distance"])
                        ],
                        [f"{e:.2f}" for e in ordered_latest["mean_error"]],
                    ],
                    align="center",
                    font=dict(size=16),
                    height=30,
                    fill_color="#f8f9fa",
                ),
            )
        ]
    )

    table.update_layout(title="Latest Calibration Summary (per OS)", margin=dict(t=60, l=0, r=0), height=250)

    return table


def generate_html_report(df, output_path="freemocap/diagnostics/calibration_diagnostics.html"):
    fig1, fig2, fig3 = generate_figures(df)
    table = generate_summary_table(df)

    template = Template(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Calibration Diagnostics Report</title>
        <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .plot-container { margin: 20px 0; }
            pre { background: #f0f0f0; padding: 10px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>Calibration Diagnostics Report</h1>

        <hr><h2>Latest Calibration Summary (per OS)</h2>
        <p>Expected square size: <strong>{{ expected }} mm</strong></p>
        <div style='max-width:1200px; margin:auto;'>{{ table|safe }}</div>

        <hr><h2>Mean Charuco Square Size Per OS</h2>
        <div class="plot-container">{{ fig1|safe }}</div>
        <p style='font-size:0.9em;'>Dashed line = expected size.</p>

        <hr><h2>Mean Charuco Square Size – versions ≥ 1.6.0</h2>
        <div class="plot-container">{{ fig2|safe }}</div>
        <p style='font-size:0.9em;'>Error bars show ±1 SD; numerical values annotated.</p>

        <hr><h2>Mean Square Size Error – versions ≥ 1.6.0</h2>
        <div class="plot-container">{{ fig3|safe }}</div>
    </body>
    </html>
    """
    )

    # Capture debug info
    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    # Re-run data loading to capture debug output
    _ = load_summary_data()

    debug_output = buffer.getvalue()
    sys.stdout = old_stdout

    rendered = template.render(
        fig1=pio.to_html(fig1, include_plotlyjs=False, full_html=False),
        fig2=pio.to_html(fig2, include_plotlyjs=False, full_html=False),
        fig3=pio.to_html(fig3, include_plotlyjs=False, full_html=False),
        table=pio.to_html(table, include_plotlyjs=False, full_html=False),
        expected=EXPECTED,
        debug_info=debug_output,
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(rendered, encoding="utf-8")
    print(f"\n✅ Calibration report written to: {output_file.absolute()}")


if __name__ == "__main__":
    df = load_summary_data()
    generate_html_report(df)
