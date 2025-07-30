# FIO Workload Optimizer
An intelligent Python script that automates Fio benchmarking to find the optimal `numjobs` and `iodepth` for maximum IOPS.

## Overview
Storage performance tuning requires finding the sweet spot for concurrency and queue depth. This script moves beyond parsing static log files and instead provides an active, iterative approach to performance optimization. It systematically runs a series of Fio benchmarks, starting with baseline parameters. It then intelligently increases `iodepth` and `numjobs`, analyzing the output of each run on-the-fly. The process automatically stops once performance gains diminish, reporting the optimal configuration that yielded the highest IOPS.

## How it Works
The script discovers the optimal numjobs and iodepth by performing the following automated steps:

1. **Initialization**: It begins with baseline values of `numjobs=1` and `iodepth=1`, using a provided Fio job file.

2. **Iterative `iodepth` Scaling**: For a given numjobs value, the script enters a loop:

    * It runs an Fio benchmark with the current numjobs and iodepth.

    * It parses the resulting IOPS from the output.

    * It then doubles the iodepth and runs the test again.

    * This iodepth loop continues until a run's IOPS do not increase by at least 5% compared to the previous one. The best iodepth for the current numjobs is then recorded.

3. **Iterative `numjobs` Scaling**: Once the optimal iodepth for a numjobs level is found, the script doubles the numjobs value.

4. **Repeat and Optimize**: It repeats the entire iodepth scaling process (Step 2) with the new, higher numjobs value.

5. **Termination**: The script concludes when increasing numjobs no longer yields a significant overall performance improvement.

6. **Final Report**: Finally, the script reports the combination of numjobs and iodepth that achieved the absolute maximum IOPS during the entire test cycle.

## Prerequisites
- Python 3.x

- Fio: You need to have fio installed.

## Usage
* Update the provided fio.job file with relevant information suitable for your environment. The script will override numjobs and iodepth.

`fio.job`
```
# This is a sample FIO job file for the optimization script.
# The script will override 'numjobs' and 'iodepth'.

[global]
ioengine=libaio
direct=1
filename=/dev/sda
filename=/dev/sdb
size=10G
runtime=300
time_based=1
group_reporting

# Add any other global options you need.
# For client/server mode, ensure fio is running in server mode on all clients:
# fio --server --daemonize=/var/run/fio.pid

[randread]
bs=8K
rw=randread
iodepth=${iodepth}
numjobs=${numjobs}
# Add other job-specific parameters here.
# For example: rate_iops, latency_target_msec, etc.
```

* Run the optimizer script.
`python3 fio_optimizer.py`

* Monitor the output. The script will print the results of each test run as it scales the parameters.
```
2025-07-30 07:11:38 [INFO] - Starting FIO performance optimization script.
2025-07-30 07:11:38 [INFO] - Using Job File: fio.job
2025-07-30 07:11:38 [INFO] - Client/Server mode enabled.
2025-07-30 07:11:38 [INFO] - ---------------- OPTIMIZING FOR NUMJOBS = 1 ----------------
2025-07-30 07:11:38 [INFO] - Running test with numjobs=1, iodepth=1...
2025-07-30 07:14:39 [INFO] - --> Result: IOPS = 812.78, 99% CLAT = 1.60 ms
2025-07-30 07:14:39 [INFO] - Running test with numjobs=1, iodepth=2...
2025-07-30 07:17:41 [INFO] - --> Result: IOPS = 1548.70, 99% CLAT = 1.73 ms
...
2025-07-30 07:32:49 [INFO] - IOPS plateaued for iodepth. Current IOPS 14725.47 is not a >5% improvement over the max of last 3 runs (14517.11).
2025-07-30 07:32:49 [INFO] - Considering CLAT, best result for numjobs=1: 14517.11 IOPS at iodepth=32
...
2025-07-30 08:09:08 [INFO] - ---------------- OPTIMIZING FOR NUMJOBS = 8 ----------------
2025-07-30 08:09:08 [INFO] - Running test with numjobs=8, iodepth=1...
2025-07-30 08:12:10 [INFO] - --> Result: IOPS = 6451.66, 99% CLAT = 2.07 ms
...
2025-07-30 08:15:12 [INFO] - Running test with numjobs=8, iodepth=4...
2025-07-30 08:18:13 [INFO] - --> Result: IOPS = 14569.07, 99% CLAT = 4.88 ms
2025-07-30 08:18:13 [INFO] - Running test with numjobs=8, iodepth=8...
2025-07-30 08:21:15 [INFO] - --> Result: IOPS = 15007.43, 99% CLAT = 10.16 ms
2025-07-30 08:21:15 [INFO] - IOPS plateaued for iodepth. Current IOPS 15007.43 is not a >5% improvement over the max of last 3 runs (14569.07).
2025-07-30 08:21:15 [INFO] - Considering CLAT, best result for numjobs=8: 14569.07 IOPS at iodepth=4
2025-07-30 08:21:15 [INFO] - ============================================================

```
* Get the final result. Once the process is complete, the script will display the best overall parameters.
```
Numjobs performance has plateaued. 
Concluding optimization.
============================================================

============================================================
FIO OPTIMIZATION COMPLETE
============================================================
Optimal numjobs: 2
Optimal iodepth: 32
Max Achieved IOPS: 14913.69
============================================================
```

## Key Features
*  Automated Tuning: Eliminates the manual process of running dozens of benchmarks.
  
*  Iterative Optimization: Intelligently scales numjobs and iodepth to find the true performance peak.
  
*  Dynamic Analysis: Analyzes results "on the go" to decide the next step.
  
*  Efficiency: Stops testing automatically once performance gains become negligible, saving time.
  
*  Clear Reporting: Provides a straightforward final report of the best parameters found.

  
