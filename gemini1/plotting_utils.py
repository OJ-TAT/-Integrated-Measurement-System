# plotting_utils.py
import matplotlib.pyplot as plt
import traceback
import os
import sys

def generate_plot_with_common_handling(plot_data_package, plot_content_function):
    """
    Handles common plot generation tasks: figure management, error handling, and saving.

    Args:
        plot_data_package (dict): A dictionary containing all necessary data and
                                  parameters for plotting. Expected keys include:
                                  'target_figure': The Matplotlib figure object (can be None).
                                  'png_file_path': Path to save the PNG file.
                                  'measurement_type_name': Full name of the measurement for titles/errors.
                                  'csv_file_path': Path to the CSV data file (for error messages).
                                  And other data needed by plot_content_function.
        plot_content_function (callable): A function that takes (figure, plot_data_package)
                                          and performs the specific plotting of data curves.
                                          This function should not handle fig.clear() or fig.savefig().

    Returns:
        bool: True if plotting and saving were successful, False otherwise.
    """
    fig = plot_data_package.get('target_figure')
    png_file_path = plot_data_package.get('png_file_path', 'plot.png')
    measurement_name = plot_data_package.get("measurement_type_name", "Plot")
    csv_file_path = plot_data_package.get('csv_file_path')

    created_temp_fig = False
    if fig is None:
        # print(f"Info ({measurement_name}): Target figure is None. Creating temporary figure for saving to {png_file_path}.")
        # Determine figsize based on measurement type or a default
        # This is a simplification; ideally, figsize could be part of plot_data_package or inferred
        figsize = (15, 9) if "Gate Transfer" in measurement_name and plot_data_package.get('live_plot_type') == 'default_live' else \
                    (12, 6) if "Diode" in measurement_name else \
                    (10, 8) # Default for Output, Breakdown, and other GT types
        fig = plt.figure(figsize=figsize)
        created_temp_fig = True
        # If fig was None, the plot_data_package sent to plot_content_function needs to be updated
        # However, plot_content_function should ideally just use the fig passed to it.
        # The live_plot_module already handles its own figure. This is for non-GUI calls.

    try:
        fig.clear() # Clear the figure before drawing new content
        plot_content_function(fig, plot_data_package) # Call the specific plotting logic

        # Ensure directory for png_file_path exists
        os.makedirs(os.path.dirname(png_file_path), exist_ok=True)
        fig.savefig(png_file_path, dpi=300)
        # print(f"  Plot for {measurement_name} saved to: {png_file_path}")
        return True
    except Exception as e:
        print(f"Error generating plot for {measurement_name}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if fig: # Try to display error on the figure
            try:
                fig.clear()
                ax_err = fig.add_subplot(111)
                error_text = f"绘制 {measurement_name} 时出错:\n{e}"
                if csv_file_path:
                     error_text += f"\n数据文件: {os.path.basename(csv_file_path)}"
                ax_err.text(0.5, 0.5, error_text, ha='center', va='center', color='red', fontsize=10, wrap=True)
                if created_temp_fig: # Save the error plot if it's a temp figure
                    fig.savefig(png_file_path, dpi=150) # Lower DPI for error image
            except Exception as e_clear:
                print(f"Additional error while displaying error on plot for {measurement_name}: {e_clear}", file=sys.stderr)
        return False
    finally:
        if created_temp_fig and fig:
            plt.close(fig) # Close the temporary figure
            # print(f"  Temporary figure for {measurement_name} closed.")

def display_error_on_plot(fig, measurement_name, error_message, csv_file_path=None):
    """
    Clears a figure and displays an error message on it.
    """
    try:
        fig.clear()
        ax_err = fig.add_subplot(111)
        full_error_text = f"绘制 {measurement_name} 时出错:\n{error_message}"
        if csv_file_path:
            full_error_text += f"\n数据文件: {os.path.basename(csv_file_path)}"
        ax_err.text(0.5, 0.5, full_error_text,
                    ha='center', va='center', color='red', fontsize=10, wrap=True)
    except Exception as e_display:
        print(f"Additional error while trying to display error on plot for {measurement_name}: {e_display}", file=sys.stderr)

