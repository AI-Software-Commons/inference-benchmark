import json
import matplotlib.pyplot as plt
import os
import argparse

# Helper function for plotting
def _create_plot(x_data, y_data, c_data, x_label, y_label, c_label_text, title, output_filename_base, annotation_data=None, annotation_format_string="{val} qps"):
    """Helper function to generate and save a scatter plot with configurable annotations."""
    if not x_data or not y_data or not c_data: # Check if any essential list is empty
        print(f"No valid data for '{title}'. Cannot generate plot.")
        return

    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(x_data, y_data, c=c_data, cmap='viridis', s=100, alpha=0.8)

    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)

    cbar = plt.colorbar(scatter)
    cbar.set_label(c_label_text)

    # Annotate each point. Default to c_data if annotation_data is not provided.
    data_for_annotation = annotation_data if annotation_data is not None else c_data
    for i, val in enumerate(data_for_annotation):
        annotation_text = annotation_format_string.format(val=val)
        plt.annotate(annotation_text, (x_data[i], y_data[i]), textcoords="offset points", xytext=(0,10), ha='center')

    plt.grid(True)
    output_filename = f'{output_filename_base}.png'
    plt.savefig(output_filename)
    print(f"Chart saved to {output_filename}")
    plt.show()
    plt.close() # Close the figure to free up memory

def _print_summary(parsed_data_points):
    """Prints a summary of the best performing data points."""
    if not parsed_data_points:
        return

    print("\n--- Benchmark Summary ---")

    # --- Find Max Throughput and Best Price/Performance---
    # Filter out points that might be missing the throughput key, though current logic prevents this.
    valid_throughput_points = [p for p in parsed_data_points if p.get("throughput") is not None]
    if valid_throughput_points:
        max_throughput_point = max(valid_throughput_points, key=lambda p: p["throughput"])
        print("\n🏆 Best Throughput / Best Price/Performance:")
        print(f"  - File: {max_throughput_point['filename']}")
        print(f"  - Throughput: {max_throughput_point['throughput']:.2f} tokens/sec")
        print(f"  - Request Rate: {max_throughput_point['request_rate']} qps")
        if max_throughput_point.get('latency') is not None:
            print(f"  - Avg Per Token Latency: {max_throughput_point['latency']:.2f} ms")
        if max_throughput_point.get('normalized_latency') is not None:
            print(f"  - Avg Normalized Latency: {max_throughput_point['normalized_latency']:.2f} ms")
        if max_throughput_point.get('cost_per_million_tokens') is not None:
            print(f"  - Cost: ${max_throughput_point['cost_per_million_tokens']:.2f} per million tokens")

    print("\n-----------------------\n")

def parse_and_plot(folder_path, instance_price_per_hour=None):
    """
    Scans a folder for JSON files, extracts benchmark metrics, and plots
    various performance and cost metrics.

    Args:
        folder_path (str): The path to the folder containing the JSON files.
        instance_price_per_hour (float, optional): The instance price per hour for cost calculation.
    """
    parsed_data_points = [] # Stores dicts of {'throughput', 'latency', 'normalized_latency', 'request_rate'}

    print(f"Scanning folder: {folder_path}")

    # Check if the folder path exists and is a directory
    if not os.path.isdir(folder_path):
        print(f"Error: The provided path '{folder_path}' is not a valid directory.")
        return

    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                metrics = data.get("metrics", {})
                throughput = metrics.get("throughput")
                latency = metrics.get("avg_per_token_latency_ms")
                normalized_latency = metrics.get("avg_normalized_time_per_output_token_ms") # New metric
                request_rate = metrics.get("request_rate")

                # Core metrics for any plot are throughput and request_rate
                if throughput is not None and request_rate is not None:
                    point_data = {
                        "throughput": throughput,
                        "latency": latency,  # Can be None
                        "normalized_latency": normalized_latency,  # Can be None
                        "request_rate": request_rate,
                        "filename": filename
                    }
                    # Calculate cost per million tokens if price is provided and throughput is valid
                    if instance_price_per_hour is not None and throughput > 0:
                        # Cost = (Price/hour * 1,000,000 tokens) / (tokens/sec * 3600 sec/hour)
                        cost_per_million_tokens = (instance_price_per_hour * 1000000) / (throughput * 3600)
                        point_data["cost_per_million_tokens"] = cost_per_million_tokens
                    elif instance_price_per_hour is not None and throughput == 0:
                        point_data["cost_per_million_tokens"] = float('inf') # Or handle as an error/skip

                    parsed_data_points.append(point_data)
                    print(f"Successfully parsed common metrics from {filename}")
                    if latency is None:
                        print(f"  - Note: 'avg_per_token_latency_ms' not found in {filename}.")
                    if normalized_latency is None:
                        print(f"  - Note: 'avg_normalized_time_per_output_token_ms' not found in {filename}.")
                else:
                    missing_core = []
                    if throughput is None:
                        missing_core.append("'throughput'")
                    if request_rate is None:
                        missing_core.append("'request_rate'")
                    print(f"Warning: Missing core metric(s) ({', '.join(missing_core)}) in {filename}. Skipping this file for plots.")

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading or parsing {file_path}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred with {file_path}: {e}")

    if not parsed_data_points:
        print("No data points with core metrics (throughput, request_rate) were parsed. Cannot generate any plots.")
        return

    # Print summary before generating plots
    _print_summary(parsed_data_points)

    # --- Plot 1: Throughput vs. Per Token Latency ---
    plot1_throughputs = []
    plot1_latencies = []
    plot1_request_rates = []
    for point in parsed_data_points:
        if point["latency"] is not None:
            plot1_throughputs.append(point["throughput"])
            plot1_latencies.append(point["latency"])
            plot1_request_rates.append(point["request_rate"])

    _create_plot(
        x_data=plot1_latencies,
        y_data=plot1_throughputs,
        c_data=plot1_request_rates,
        x_label='Average Per Token Latency (ms)',
        y_label='Throughput (output tokens/sec)',
        c_label_text='Request Rate (QPS)',
        title='Throughput vs. Per Token Latency',
        output_filename_base='throughput_vs_latency'
    )

    # --- Plot 2: Throughput vs. Normalized Per Token Latency ---
    plot2_throughputs = []
    plot2_normalized_latencies = []
    plot2_request_rates = []
    for point in parsed_data_points:
        if point["normalized_latency"] is not None:
            plot2_throughputs.append(point["throughput"])
            plot2_normalized_latencies.append(point["normalized_latency"])
            plot2_request_rates.append(point["request_rate"])

    _create_plot(
        x_data=plot2_normalized_latencies,
        y_data=plot2_throughputs,
        c_data=plot2_request_rates,
        x_label='Average Normalized Time Per Output Token (ms)',
        y_label='Throughput (output tokens/sec)',
        c_label_text='Request Rate (QPS)',
        title='Throughput vs. Normalized Per Token Latency',
        output_filename_base='throughput_vs_normalized_latency'
    )

    # --- Plot 3: Cost per Million Output Tokens vs. Normalized Per Token Latency ---
    if instance_price_per_hour is not None:
        plot3_normalized_latencies = []
        plot3_costs_per_million_tokens = []
        plot3_request_rates = []
        for point in parsed_data_points:
            if point.get("normalized_latency") is not None and point.get("cost_per_million_tokens") is not None:
                plot3_normalized_latencies.append(point["normalized_latency"])
                plot3_costs_per_million_tokens.append(point["cost_per_million_tokens"])
                plot3_request_rates.append(point["request_rate"])

        _create_plot(
            x_data=plot3_normalized_latencies,
            y_data=plot3_costs_per_million_tokens,
            c_data=plot3_request_rates,
            x_label='Average Normalized Time Per Output Token (ms)',
            y_label='$ per Million Output Tokens',
            c_label_text='Request Rate (QPS)',
            title='Cost per Million Output Tokens vs. Normalized Latency',
            output_filename_base='cost_vs_normalized_latency',
            annotation_data=plot3_costs_per_million_tokens,
            annotation_format_string="${val:.2f}"
        )
    else:
        print("Skipping cost plot as --instance-price-per-hour was not provided.")

if __name__ == '__main__':
    # Set up an argument parser to get the folder path from the command line
    parser = argparse.ArgumentParser(description="Parse all benchmark JSON files in a folder and generate a plot.")
    parser.add_argument("folder_path", type=str, help="The path to the folder containing the JSON files.")
    parser.add_argument("--instance-price-per-hour", type=float, default=None,
                        help="Optional: Instance price per hour (e.g., 2.50 for $2.50/hour) to calculate cost per million tokens.")

    args = parser.parse_args()

    # Call the function with the folder path provided by the user
    parse_and_plot(args.folder_path, args.instance_price_per_hour)
