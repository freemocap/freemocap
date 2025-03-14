from pathlib import Path
import pandas as pd 


import plotly.express as px
def plot_jerk_trends(total_df):
    # Reset index for easy handling in Plotly
    plot_df = total_df[total_df['name']=='total'].copy()
    # Line plot of jerk trends per joint across versions
    fig = px.line(plot_df, x="version", y="mean_jerk", color="data_stage",
                  title="Jerk Trends Across Versions", markers=True)

    return fig


def format_jerk_table(total_df):
    """
    Creates separate tables for each data stage with color mapping based on differences 
    from v1.2.0 values using a scientific colormap, with improved aesthetics.
    """
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    
    # Extract unique data_stages
    data_stages = sorted(total_df['data_stage'].unique())
    
    # Set up scientific colormaps - using RdBu_r (reversed Red-Blue) which is perceptually uniform
    cmap_diverging = plt.cm.RdBu_r
    
    # Create a function to apply color based on percentage difference from reference
    def color_diff_from_reference(val, ref_val):
        if pd.isna(val) or pd.isna(ref_val) or ref_val == 0:
            return ''
        
        # Calculate percentage difference
        pct_diff = (val - ref_val) / ref_val * 100
        
        # Cap the difference for extreme values (adjust this range as needed)
        max_pct = 60.0  # Increased from 50 to reduce overly intense colors
        
        # Use a non-linear scaling to improve color distribution
        # This reduces the intensity for moderate differences
        if pct_diff > 0:  # Worse than reference
            # Use square root scaling for smoother gradient
            normalized_diff = min(np.sqrt(pct_diff / max_pct), 1.0)
            norm_val = 0.5 + (normalized_diff * 0.5)  # Map to 0.5-1.0 range (red half)
        elif pct_diff < 0:  # Better than reference
            # Use square root scaling for smoother gradient
            normalized_diff = min(np.sqrt(abs(pct_diff) / max_pct), 1.0)
            norm_val = 0.5 - (normalized_diff * 0.5)  # Map to 0.0-0.5 range (blue half)
        else:  # Equal to reference
            norm_val = 0.5  # Middle point (white/neutral)
        
        # Get RGB color from the colormap
        rgba = cmap_diverging(norm_val)
        rgb = rgba[:3]  # Extract RGB (ignore alpha)
        
        # Add a slight transparency to soften the colors
        # Convert to rgba with transparency
        return f'background-color: rgba({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)}, 0.85)'
    
    # Function to create a styled table for each data stage
    def create_stage_table(stage):
        # Filter data for this stage
        stage_df = total_df[total_df['data_stage'] == stage]
        
        # Pivot to get versions as columns
        pivot_df = stage_df.pivot(index="name", columns="version", values="mean_jerk")
        
        # Get reference values (1.2.0)
        reference_values = pivot_df['1.2.0']
        
        # Define styling function
        def style_columns(col):
            if col.name == '1.2.0':
                # Neutral color for reference column
                return ['background-color: #f7f7f7' for _ in col]
            else:
                # Apply coloring based on difference from reference
                return [color_diff_from_reference(val, reference_values[idx]) 
                        for idx, val in col.items()]
        
        # Function to bold the total row
        def bold_total(s):
            return ['font-weight: bold' if s.name == "total" else '' for _ in s]
        
        # Style the table
        styled_table = (
            pivot_df.style
            .set_table_styles([
                {"selector": "thead th", "props": [("font-weight", "bold"), 
                                                  ("background-color", "#f4f4f4"), 
                                                  ("text-align", "center"),
                                                  ("padding", "8px 5px")]},
                {"selector": "tbody td", "props": [("text-align", "center"), 
                                                  ("min-width", "60px"), 
                                                  ("padding", "6px 5px")]},
                {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#f9f9f9")]},
                {"selector": "caption", "props": [("caption-side", "top"), 
                                                 ("font-weight", "bold"),
                                                 ("font-size", "16px"),
                                                 ("padding", "15px 0 10px 0"),
                                                 ("text-align", "left")]},
                {"selector": "table", "props": [("border-collapse", "separate"),
                                               ("border-spacing", "0"),
                                               ("width", "100%"),
                                               ("margin-bottom", "25px"),
                                               ("box-shadow", "0 1px 3px rgba(0,0,0,0.1)")]}
            ])
            .apply(style_columns, axis=0)
            .apply(bold_total, axis=1)
            .format("{:.2f}")
        )
        
        # Add a title for the table with stage name highlighted
        styled_table.set_caption(f"{stage.capitalize()} Data - Jerk Values")
        
        return styled_table.to_html()
    
    # Create HTML for all tables with a color legend and page title
    html_output = """
    <div style="max-width: 1200px; margin: 0 auto; font-family: Arial, sans-serif;">
        <h2 style="text-align: center; margin: 20px 0;">Summary Table: Jerk Across Versions</h2>
        
        <div style="text-align: center; margin: 25px 0; padding: 10px; background-color: #f0f0f0; border-radius: 5px; font-weight: bold; font-size: 14px;">
            Jerk Values: Blue = Improvement from v1.2.0, Red = Degradation from v1.2.0
        </div>
    """
    
    # Add tables for each data stage
    for stage in data_stages:
        html_output += f"""
        <div style="margin-bottom: 40px;">
            {create_stage_table(stage)}
        </div>
        """
    
    # Close the container div
    html_output += "</div>"
    
    return html_output



from jinja2 import Template
from packaging import version

def generate_html_report(total_df, output_path="diagnostic_report.html"):
    # Extract versions and sort them semantically using packaging.version
    version_list = total_df['version'].unique()
    # Separate 'current' from version numbers
    current_version = 'current' if 'current' in version_list else None
    numeric_versions = [v for v in version_list if v != 'current']
    
    # Sort numeric versions semantically
    sorted_versions = sorted(numeric_versions, key=lambda x: version.parse(x))
    
    # Add 'current' at the end if it exists
    if current_version:
        sorted_versions.append(current_version)
    
    # Convert version column to categorical for proper ordering
    total_df['version'] = pd.Categorical(
        total_df['version'], 
        categories=sorted_versions, 
        ordered=True
    )

    jerk_plot = plot_jerk_trends(total_df).to_html(full_html=False)
    html_table = format_jerk_table(total_df)

    html_template = """
    <html>
    <head>
        <title>Motion Capture Diagnostic Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .plot { margin-bottom: 40px; }
            .table-container { margin-top: 40px; }
        </style>
    </head>
    <body>
        <h1>Motion Capture Diagnostic Report</h1>
        
        <h2>Jerk Trends Across Versions</h2>
        <div class="plot">{{ jerk_plot|safe }}</div>
        
        <h2>Summary Table: Jerk Across Versions</h2>
        <div class="table-container">{{ html_table|safe }}</div>
    </body>
    </html>
    """

    # Render the HTML
    template = Template(html_template)
    rendered_html = template.render(jerk_plot=jerk_plot, html_table=html_table)

    # Save to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print(f"Report saved at: {output_path}")
    
if __name__ == "__main__":

    path_to_diagnostics_folder =  Path(r'freemocap/diagnostics/version_diagnostics')

    results_list = list(path_to_diagnostics_folder.glob('*.csv'))
    total_df = pd.DataFrame()

    for result in results_list:
        result_df = pd.read_csv(result)
        total_df = pd.concat([total_df, result_df], ignore_index=True)

    output_report_path = path_to_diagnostics_folder / "diagnostic_report.html"
    generate_html_report(total_df, output_report_path)    