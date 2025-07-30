#!/usr/bin/env python3

import subprocess
import json
import logging
import sys
import os
from typing import Union, Tuple, List
from collections import deque

# ==============================================================================
# FIO CONFIGURATION - !!! PLEASE EDIT THESE VALUES !!!
# ==============================================================================
# 1. Path to your FIO job file.
FIO_JOB_FILE = "fio.job"

# 2. (Optional) Path to a file containing a list of clients, one per line.
#    - To run locally, leave this string empty: FIO_CLIENT_FILE = ""
#    - To use clients, set the path: FIO_CLIENT_FILE = "clients.txt"
#    NOTE: You must start 'fio --server' on each client machine first.
FIO_CLIENT_FILE = "client.txt"

# ==============================================================================
# SCRIPT PARAMETERS - (Advanced users can modify these)
# ==============================================================================
# The runtime for each individual fio test in seconds.
#FIO_RUNTIME_SECONDS = 120

# The threshold for what is considered a 'significant' IOPS improvement (5%).
IOPS_IMPROVEMENT_THRESHOLD = 1.05

# The executable name or path for fio.
FIO_EXECUTABLE = "fio"

# Iterations and not abosolute values
MIN_NUMJOBS_RUNS = 4
MIN_IODEPTH_RUNS = 4
# ==============================================================================


def setup_logging():
    """Configures logging to print informative messages to the console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

def read_clients_from_file(filepath: str) -> List[str]:
    """
    Reads a list of clients from a file, one client per line.
    
    Args:
        filepath: The path to the client file.
    
    Returns:
        A list of client hostnames or IPs. Returns an empty list if file is not found.
    """
    if not filepath:
        return []
    try:
        with open(filepath, 'r') as f:
            # Read each line, strip whitespace, and ignore empty lines or comments
            clients = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return clients
    except FileNotFoundError:
        logging.warning(f"Client file '{filepath}' not found. Will run in local mode.")
        return []

def parse_fio_json(json_output: str) -> Tuple[Union[float, None], Union[float, None]]:
    """
    Parses FIO JSON, intelligently handling both single-node and aggregated multi-client output.
    """
    try:
        data = json.loads(json_output)
        target_job = None
        latency_metric_used = "99th percentile CLAT"

        # Priority 1: Find the aggregated "All clients" block for multi-client runs.
        if "client_stats" in data:
            for job in data["client_stats"]:
                if job.get("jobname") == "All clients":
                    target_job = job
                    #logging.info("Found aggregated 'All clients' block for parsing.")
                    break
        
        if not target_job:
            target_job = data["client_stats"][0]
            #logging.info("Parsing first job in 'jobs' array (local run).")

        if not target_job:
            logging.error("Could not find a suitable job block to parse in FIO output.")
            return None, None

        # Determine if it's a read or write job and extract metrics.
        if "read" in target_job and target_job["read"]["iops"] > 0:
            iops = target_job["read"]["iops"]
            clat_ns_data = target_job["read"]["clat_ns"]
        elif "write" in target_job and target_job["write"]["iops"] > 0:
            iops = target_job["write"]["iops"]
            clat_ns_data = target_job["write"]["clat_ns"]
        else:
            logging.error(f"Target job '{target_job.get('jobname')}' has no read/write stats.")
            return None, None

        # In aggregated "All clients" view, percentiles are not available. Use mean.
        if "percentile" in clat_ns_data:
            clat_ns = clat_ns_data["percentile"]["99.000000"]
        else:
            clat_ns = clat_ns_data["mean"]
            #latency_metric_used = "mean CLAT (percentiles not available in aggregate view)"

        #logging.info(f"Using {latency_metric_used} for latency check.")
        return iops, clat_ns / 1_000_000  # convert ns to ms

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logging.error(f"Error parsing fio JSON output: {e}")
        logging.debug(f"Problematic JSON string: {json_output[:1000]}") # Log first 1k chars
        return None, None

def run_fio(numjobs: int, iodepth: int, clients: List[str]) -> Tuple[Union[float, None], Union[float, None]]:
    """
    Constructs and executes a fio command using a job file and optional clients.
    """
    logging.info(f"Running test with numjobs={numjobs}, iodepth={iodepth}...")

    nj = str(numjobs)
    iod = str(iodepth)
    os.environ['numjobs'] = nj
    os.environ['iodepth'] = iod
    command = [
        FIO_EXECUTABLE,
        FIO_JOB_FILE,
        f"--output-format=json",
        ]

    # Add client arguments if the list is not empty
    if clients:
        #for client in clients:
            #command.append(f"--client={client}")
            command.append(f"--client={FIO_CLIENT_FILE}")

    try:
        process = subprocess.run(
            command, capture_output=True, text=True, check=True, encoding="utf-8"
        )
        stdout = process.stdout.strip()

        # deregister the env variables

        #print (process.stdout)
        if not stdout:
            logging.error("FIO command produced no output.")
            logging.error(f"Command: {' '.join(command)}")
            logging.error(f"FIO Error Message (stderr):\n{process.stderr}")
            return None, None

        # Handle cases where fio outputs multiple JSON objects concatenated together.
        # We find the last valid JSON object and parse that one.
        if stdout.count('"jobname"') >= 1:
            #logging.warning("Multiple JSON objects detected. Parsing the final aggregated output.")
            last_json_start = stdout.rfind("version")
            #print (last_json_start)
            stdout = stdout[last_json_start:]
            stdout = "{ \"" + stdout
            #print (stdout)
        
        return parse_fio_json(stdout)

    except FileNotFoundError:
        logging.error(f"FIO executable not found at '{FIO_EXECUTABLE}'. Please check your path.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error("FIO command failed with a non-zero exit code.")
        logging.error(f"Command: {' '.join(command)}")
        logging.error(f"Error Message. Stderr:\n{e.stderr}")
        return None, None


def main():
    """Main function to orchestrate the fio optimization process."""
    setup_logging()
    
    if not os.path.exists(FIO_JOB_FILE):
        logging.error(f"FIO job file not found at '{FIO_JOB_FILE}'. Please fix the path.")
        sys.exit(1)
    
    # Read the list of clients from the specified file
    clients = read_clients_from_file(FIO_CLIENT_FILE)

    logging.info("Starting FIO performance optimization script.")
    logging.info(f"Using Job File: {FIO_JOB_FILE}")

    if clients:
        logging.info(f"Client/Server mode enabled.")
        #logging.info(f"Client/Server mode enabled. Using clients: {', '.join(clients)}")
    else:
        logging.info("No client file specified or found. Running in local mode.")
    
    optimal_nj, optimal_id, best_overall_iops, last_nj_best_iops = 0, 0, 0.0, 0.0

    nj_iops_history = deque(maxlen=3)
    nj_run_count = 0
    current_nj = 1
    while current_nj <= 128:
        nj_run_count += 1
        logging.info("-" * 16 + f" OPTIMIZING FOR NUMJOBS = {current_nj} " + "-" * 16)
        best_iops_for_nj, best_id_for_nj = 0.0, 0
        id_results_history = deque(maxlen=3)
        id_run_count = 0

        current_id = 1
        while current_id <= 256:
            id_run_count += 1
            # Pass the client list to the run_fio function
            iops, clat_ms = run_fio(current_nj, current_id, clients)
            if iops is None:
                logging.error("Stopping optimization due to a FIO error.")
                return

            logging.info(f"--> Result: IOPS = {iops:.2f}, 99% CLAT = {clat_ms:.2f} ms")

            #Consider omitting len(id_result_history) == 3
            if id_run_count >= MIN_IODEPTH_RUNS and len(id_results_history) == 3:
                max_iops_of_last_3 = max(r['iops'] for r in id_results_history)
                if iops < max_iops_of_last_3 * IOPS_IMPROVEMENT_THRESHOLD:
                    logging.info(f"IOPS plateaued for iodepth. Current IOPS {iops:.2f} is not a >5% improvement over the max of last 3 runs ({max_iops_of_last_3:.2f}).")
                    break
            # Store the current result
            id_results_history.append({'iops': iops, 'clat': clat_ms})

            # Track the best performance found so far for this numjobs value
            if iops > best_iops_for_nj:
                best_iops_for_nj = iops
                best_id_for_nj = current_id
                # And also track the best performance found overall
                if best_iops_for_nj > best_overall_iops:
                    best_overall_iops = best_iops_for_nj
                    optimal_nj = current_nj
                    optimal_id = best_id_for_nj
            
            current_id *= 2

        logging.info(f"Considering CLAT, best result for numjobs={current_nj}: {best_iops_for_nj:.2f} IOPS at iodepth={best_id_for_nj}")

        # (NEW) Check for numjobs performance plateau after minimum runs
        if nj_run_count >= MIN_NUMJOBS_RUNS and len(nj_iops_history) == 3:
            max_iops_of_last_3_nj = max(nj_iops_history)
            if best_iops_for_nj < max_iops_of_last_3_nj * IOPS_IMPROVEMENT_THRESHOLD:
                #logging.info("=" * 60 + "\nNumjobs performance has plateaued. \nBest IOPS for nj={current_nj} ({best_iops_for_nj:.2f}) is not a >5% improvement over the max of previous runs ({max_iops_of_last_3_nj:.2f}). \nConcluding optimization.\n" + "=" * 60)
                break

        nj_iops_history.append(best_iops_for_nj)
        current_nj *= 2

    print("\n" + "=" * 60)
    print("FIO OPTIMIZATION COMPLETE")
    print("=" * 60)
    print(f"Optimal numjobs: {optimal_nj}")
    print(f"Optimal iodepth: {optimal_id}")
    print(f"Max Achieved IOPS: {best_overall_iops:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
