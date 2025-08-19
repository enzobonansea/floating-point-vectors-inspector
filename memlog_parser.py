#!/usr/bin/env python3
from __future__ import annotations
import bisect
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, TextIO
from tqdm import tqdm
from multiprocessing import cpu_count, get_context
import time

# ---------------- Regex ----------------
ALLOC_HEADER_RE = re.compile(r"^Start\s+0x([0-9a-fA-F]+),\s+size\s+(\d+)")
STORE_RE = re.compile(r"^0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)")

# ---------------- Memory monitoring without psutil ----------------
def get_memory_percent():
    """Get memory usage percentage from /proc/meminfo (Linux only)"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            total = 0
            available = 0
            for line in lines:
                if line.startswith('MemTotal:'):
                    total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    available = int(line.split()[1])
                    break
            if total > 0:
                used_percent = 100 * (1 - available / total)
                return used_percent
    except:
        pass
    return 0  # Return 0 if we can't determine memory usage

# -------------------------------------------------------

class LiveAlloc:
    """Represents an active memory block between ALLOC and FREE."""
    __slots__ = (
        "start",
        "size",
        "end",
        "store_count",
        "aligned32",
        "aligned64",
        "base_core",
        "store_path",
        "temp_file_offset",  # Offset in shared temp file
        "temp_file_size",    # Size written to temp file
        "usage_num",         # Usage number for this address
    )

    def __init__(self, start: int, size: int, base_core: str, out_dir: Path, usage_num: int):
        self.start = start
        self.size = size
        self.end = start + size
        self.aligned32 = True
        self.aligned64 = True
        self.base_core = base_core
        self.store_count = 0
        self.store_path = out_dir / f".{base_core}.tmp"
        self.temp_file_offset = -1  # Will be set when first store written
        self.temp_file_size = 0
        self.usage_num = usage_num

    def write_store(self, addr_hex: str, value_hex: str, temp_file: TextIO) -> None:
        addr = int(addr_hex, 16)
        offset = addr - self.start
        
        # Track position if first write
        if self.temp_file_offset == -1:
            self.temp_file_offset = temp_file.tell()
        
        line = f"0x{addr_hex.lower()} 0x{value_hex.lower()} {offset}\n"
        temp_file.write(line)
        self.temp_file_size += len(line.encode('utf-8'))
        self.store_count += 1
        
        if self.aligned32 and offset % 4 != 0:
            self.aligned32 = False
        if self.aligned64 and offset % 8 != 0:
            self.aligned64 = False

    def close_and_finalize(self, out_dir: Path, temp_file_path: Path) -> None:
        if self.store_count == 0:
            # No STOREs = no file needed
            return
        
        # Determine type based on alignment
        type_name = "object"
        if self.aligned32:
            type_name = "double" if self.aligned64 else "float"
        
        # Create new name with usage number and .stores extension
        # Format: 0xaddress_size_type_N.stores
        target = out_dir / f"{self.base_core}_{type_name}_{self.usage_num}.stores"
        
        # Copy data from shared temp file to individual file
        with open(temp_file_path, "rb") as src:
            src.seek(self.temp_file_offset)
            with open(target, "wb") as dst:
                # Copy in chunks to handle large data
                remaining = self.temp_file_size
                chunk_size = 8192
                while remaining > 0:
                    to_read = min(chunk_size, remaining)
                    data = src.read(to_read)
                    if not data:
                        break
                    dst.write(data)
                    remaining -= len(data)

# -------------------------------------------------------

def parse_log(log_path: str | os.PathLike) -> Path:
    """Parses a huge Valgrind log; outputs files only for ALLOCs that get STOREs."""
    log_path = Path(log_path)
    if not log_path.is_file():
        raise FileNotFoundError(log_path)

    out_dir = log_path.with_suffix(log_path.suffix + ".parsed")
    out_dir.mkdir(exist_ok=True)

    live_allocs: Dict[int, List[LiveAlloc]] = defaultdict(list)
    starts_sorted: List[int] = []
    live_list: List[LiveAlloc] = []
    # Track usage count per address
    address_usage_count: Dict[int, int] = defaultdict(int)

    def _add(alloc: LiveAlloc):
        idx = bisect.bisect_left(starts_sorted, alloc.start)
        starts_sorted.insert(idx, alloc.start)
        live_list.insert(idx, alloc)
        live_allocs[alloc.start].append(alloc)

    def _remove(alloc: LiveAlloc):
        idx = live_list.index(alloc)
        starts_sorted.pop(idx)
        live_list.pop(idx)
        live_allocs[alloc.start].pop()

    # Create a single shared temporary file for all stores
    temp_file_path = out_dir / ".shared_temp_stores.tmp"
    
    file_size = log_path.stat().st_size
    with tqdm(total=file_size, desc="Parsing log", unit="B", unit_scale=True) as pbar, \
         log_path.open("r", encoding="utf-8", errors="ignore") as fh, \
         temp_file_path.open("w", encoding="utf-8") as temp_file:

        inside_alloc = inside_free = False

        for line in fh:
            pbar.update(len(line))

            # STORE ------------------------------------------------------
            m_store = STORE_RE.match(line)
            if m_store:
                addr_hex, value_hex = m_store.groups()
                addr_int = int(addr_hex, 16)
                
                # Find the allocation that contains this address
                # Start with the most likely candidate using bisect
                pos = bisect.bisect_right(starts_sorted, addr_int) - 1
                
                # Check if this address falls within any live allocation
                found = False
                if pos >= 0:
                    # Check the allocation at pos first (most likely candidate)
                    alloc = live_list[pos]
                    if alloc.start <= addr_int < alloc.end:
                        alloc.write_store(addr_hex, value_hex, temp_file)
                        found = True
                
                # If not found in the expected position, search all allocations
                # This handles cases where allocations might overlap or have gaps
                if not found:
                    for alloc in live_list:
                        if alloc.start <= addr_int < alloc.end:
                            alloc.write_store(addr_hex, value_hex, temp_file)
                            found = True
                            break
                
                # If still not found, the store is outside any live allocation
                if not found:
                    raise ValueError(
                        f"STORE at address 0x{addr_hex} with value 0x{value_hex} "
                        f"does not belong to any live allocation. "
                        f"Current live allocations: {len(live_list)} blocks"
                    )
                continue

            # ALLOC / FREE delimiters -----------------------------------
            if line.startswith("===ALLOC START==="):
                inside_alloc = True; continue
            if line.startswith("===ALLOC END==="):
                inside_alloc = False; continue
            if line.startswith("===FREE START==="):
                inside_free = True; continue
            if line.startswith("===FREE END==="):
                inside_free = False; continue
            
            # ALLOC header ----------------------------------------------
            if inside_alloc:
                m_alloc = ALLOC_HEADER_RE.match(line)
                if m_alloc:
                    start_hex, size_str = m_alloc.groups()
                    start_int = int(start_hex, 16)
                    size_int = int(size_str)
                    base_core = f"0x{start_hex.lower()}_{size_int}"
                    # Increment usage count for this address
                    address_usage_count[start_int] += 1
                    _add(LiveAlloc(start_int, size_int, base_core, out_dir, address_usage_count[start_int]))
                continue

            # FREE header -----------------------------------------------
            if inside_free:
                m_free = ALLOC_HEADER_RE.match(line)
                if m_free:
                    start_hex, _size_str = m_free.groups()
                    start_int = int(start_hex, 16)
                    stack = live_allocs.get(start_int)
                    if stack:
                        alloc = stack[-1]
                        alloc.close_and_finalize(out_dir, temp_file_path)
                        _remove(alloc)
                continue

    # Finaliza los allocs vivos sin FREE
    for alloc in list(live_list):
        alloc.close_and_finalize(out_dir, temp_file_path)
        _remove(alloc)
    
    # Clean up the shared temp file
    if temp_file_path.exists():
        temp_file_path.unlink()

    # Write status to a log file that persists outside SPEC's redirection
    status_log = Path("/tmp/memlog_parser_status.log")
    with open(status_log, "a") as log:
        log.write(f"[{log_path.name}] Parsing completed. Files in: {out_dir}\n")
    
    print(f"[parse_log] Finished. Files are in: {out_dir}")
    return out_dir

# Process parsed files
def process_compression(parsed_dir: str | os.PathLike) -> Path:
    parsed_dir = Path(parsed_dir)
    if not parsed_dir.is_dir():
        raise NotADirectoryError(parsed_dir)

    analyzed_file = parsed_dir / (parsed_dir.name + ".analyzed")
    summary_file = parsed_dir / (parsed_dir.name + ".summary")

    # Simple counting: total_buffers = qty of .stores files, buffers_processed = qty of .compression files
    total_buffers = sum(1 for f in parsed_dir.iterdir() if f.is_file() and f.name.endswith('.stores'))
    buffers_processed = sum(1 for f in parsed_dir.iterdir() if f.is_file() and f.name.endswith('.compression'))

    buffers_compressed = 0  # Will count successful compressions
    total_compressible_size = 0
    total_compressed_size = 0


    with open(analyzed_file, "w") as outfile:
        # Imprimir encabezado CSV - updated column names
        print("filename,element_type,buffer_size,all_zeros,line_too_big_error,footer_full_error,ulr_miss_qty,footer_write_qty,footer_read_qty,size_reduced_percentage,lossless,file_size,total_lines", file=outfile)

        for file in parsed_dir.iterdir():
            if not file.is_file():
                continue
            
            # Skip the analyzed and summary files themselves
            if file == analyzed_file or file == summary_file:
                continue
            
            fname = file.name
            # Skip if not a .stores file
            if not fname.endswith('.stores'):
                continue

            dist_path = file
            comp_path = file.with_suffix(file.suffix + ".compression")

            # Parse filename pattern: 0xaddress_size_type_N.stores
            parts = fname.replace('.stores', '').split('_')
            
            # Extract buffer_size (should be the second element)
            try:
                if len(parts) >= 4:  # We expect at least: address, size, type, N
                    buffer_size = int(parts[1])
                else:
                    buffer_size = ""
            except (IndexError, ValueError):
                buffer_size = ""
            
            # Extract element type (should be the third element)
            if len(parts) >= 4:
                type_part = parts[2]  # Get the type part
                if type_part in ["float", "double", "object"]:
                    element_type = type_part
                else:
                    element_type = "unknown"
            else:
                element_type = "unknown"

            # Verificar si todas las segundas columnas son 0x0
            all_zeros = True
            total_lines = 0
            with open(dist_path, "r") as infile:
                for line in infile:
                    total_lines += 1
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] != "0x0":
                        all_zeros = False

            ulr = ""
            footer_write_qty = ""
            footer_read_qty = ""
            size_reduced_vals = []
            lossless = False
            line_too_big_error = False
            footer_full_error = False
            partially_compressed_lines = False

            # Leer archivo .compression
            try:
                with open(comp_path, "r") as compfile:
                    output = compfile.read()
                    
                    # Check for errors
                    if "LineTooBigError" in output or "Line too big" in output:
                        line_too_big_error = True
                    if "FooterFullError" in output:
                        footer_full_error = True
                    
                    # Parse values
                    for line in output.splitlines():
                        if "ULR miss qty:" in line:
                            try:
                                ulr = int(line.split(':')[1].strip())
                            except:
                                ulr = ""
                        if "Footer write qty:" in line:
                            try:
                                footer_write_qty = int(line.split(':')[1].strip())
                            except:
                                footer_write_qty = ""
                        if "Footer read qty:" in line:
                            try:
                                footer_read_qty = int(line.split(':')[1].strip())
                            except:
                                footer_read_qty = ""
                        if "Size reduced by" in line:
                            try:
                                size = float(line.split()[3].replace('%', ''))
                                size_reduced_vals.append(size)
                            except:
                                pass
                        if "Lossless:" in line:
                            if "True" in line:
                                lossless = True
                                buffers_compressed += 1
            except:
                # File doesn't exist or can't be read - leave defaults
                pass

            size_reduced_percentage = ""
            if len(size_reduced_vals) >= 2:
                size_reduced_percentage = size_reduced_vals[1]
            elif size_reduced_vals:
                size_reduced_percentage = size_reduced_vals[0]

            file_size = os.path.getsize(dist_path)

            # Calculate sizes for summary
            if isinstance(buffer_size, int):
                if element_type != "object":
                    # Only float and double types are compressible
                    total_compressible_size += buffer_size
                    # If compression was successful, use compressed size
                    if lossless and isinstance(size_reduced_percentage, (int, float, str)) and str(size_reduced_percentage).replace('.', '', 1).isdigit():
                        reduced = float(size_reduced_percentage)
                        total_compressed_size += buffer_size * (1 - reduced / 100)
                    else:
                        # If not compressed but processed, use uncompressed size
                        total_compressed_size += buffer_size
                # object type files don't contribute to compressed size (sum 0)

            print(f"{fname},{element_type},{buffer_size},{all_zeros},{line_too_big_error},{footer_full_error},{ulr},{footer_write_qty},{footer_read_qty},{size_reduced_percentage},{lossless},{file_size},{total_lines}", file=outfile)

    with open(summary_file, "w") as summary:
        print("total_buffers,buffers_processed,buffers_compressed,total_compressible_size,total_compressed_size", file=summary)
        print(f"{total_buffers},{buffers_processed},{buffers_compressed},{total_compressible_size},{int(total_compressed_size)}", file=summary)

    # Create human-readable report file
    report_file = parsed_dir / (parsed_dir.name + ".report")
    with open(report_file, "w") as report:
        # Calculate key metrics
        compression_rate = (buffers_compressed / buffers_processed * 100) if buffers_processed > 0 else 0
        size_reduction = ((total_compressible_size - total_compressed_size) / total_compressible_size * 100) if total_compressible_size > 0 else 0
        skipped_buffers = total_buffers - buffers_processed
        
        print("=" * 60, file=report)
        print("MEMORY COMPRESSION ANALYSIS REPORT", file=report)
        print("=" * 60, file=report)
        print(file=report)
        
        print("QUICK SUMMARY:", file=report)
        print("-" * 40, file=report)
        print(f"✓ Found {total_buffers} memory allocations", file=report)
        print(f"✓ Attempted compression on {buffers_processed} buffers", file=report)
        print(f"✓ Successfully compressed {buffers_compressed} buffers ({compression_rate:.1f}% success rate)", file=report)
        print(f"✓ Skipped {skipped_buffers} object-type buffers (not compressible)", file=report)
        print(file=report)
        
        print("SIZE REDUCTION:", file=report)
        print("-" * 40, file=report)
        print(f"Original size: {total_compressible_size:,} bytes", file=report)
        print(f"Compressed size: {int(total_compressed_size):,} bytes", file=report)
        print(f"Space saved: {int(total_compressible_size - total_compressed_size):,} bytes ({size_reduction:.1f}%)", file=report)
        print(file=report)
        
        print("WHAT THIS MEANS:", file=report)
        print("-" * 40, file=report)
        if compression_rate > 70:
            print("✓ EXCELLENT: Most buffers compressed successfully!", file=report)
            print("  Your data has high redundancy/patterns.", file=report)
        elif compression_rate > 40:
            print("⚠ MODERATE: Some buffers compressed well.", file=report)
            print("  Mixed data patterns - some redundant, some random.", file=report)
        else:
            print("✗ POOR: Few buffers compressed successfully.", file=report)
            print("  Data appears mostly random or unique.", file=report)
        print(file=report)
        
        if size_reduction > 50:
            print(f"✓ Compression saved {size_reduction:.1f}% - significant memory reduction!", file=report)
        elif size_reduction > 20:
            print(f"⚠ Compression saved {size_reduction:.1f}% - moderate memory reduction.", file=report)
        else:
            print(f"✗ Compression saved only {size_reduction:.1f}% - minimal benefit.", file=report)
        print(file=report)
        
        print("=" * 60, file=report)
        print("FILES GENERATED:", file=report)
        print("-" * 40, file=report)
        print(f"• {analyzed_file.name} - Detailed per-buffer analysis", file=report)
        print(f"• {summary_file.name} - Summary statistics (CSV)", file=report)
        print(f"• {report_file.name} - This report", file=report)
        print(f"• *.stores files - Raw memory store data", file=report)
        print(f"• *.compression files - Compression results", file=report)
        print(file=report)
        
        print("COLUMN REFERENCE:", file=report)
        print("-" * 40, file=report)
        print("Summary columns:", file=report)
        print("  • total_buffers: All memory allocations found", file=report)
        print("  • buffers_processed: Buffers we tried to compress", file=report)
        print("  • buffers_compressed: Successfully compressed (lossless)", file=report)
        print("  • total_compressible_size: Original size (float+double)", file=report)
        print("  • total_compressed_size: Size after compression", file=report)
        print(file=report)
        print("Analyzed columns:", file=report)
        print("  • filename: Buffer file name (address_size_type_N.stores)", file=report)
        print("  • element_type: float/double/object", file=report)
        print("  • buffer_size: Allocation size in bytes", file=report)
        print("  • all_zeros: Whether all values are 0x0", file=report)
        print("  • lossless: Compression succeeded without data loss", file=report)
        print("  • size_reduced_percentage: Compression ratio achieved", file=report)
        print("=" * 60, file=report)

    return analyzed_file
        


# Helper function for parallel compression
def compress_file(file: Path) -> tuple:
    """Compress a single file and return result tuple.
    Returns (file, success, error_msg, is_unrecoverable)
    """
    import subprocess
    import sys
    
    filename = file.name
    # Parse filename to determine type: 0xaddress_size_type_N.stores
    if filename.endswith('.stores'):
        parts = filename.replace('.stores', '').split('_')
        if len(parts) >= 4:
            type_part = parts[2]  # Extract the type
            if type_part == 'object':
                return (file, False, f"Buffers containing objects are not compressible", False)
            elif type_part in ['float', 'double']:
                compression_output_file = f"{file}.compression"
                try:
                    # Run subprocess with output file argument
                    result = subprocess.run(
                        ["/usr/mmu_compressor", str(file), "--output-file", compression_output_file],
                        capture_output=False, # Don't capture output since mmu_compressor writes directly to file
                        text=True,
                        check=True  # Raise CalledProcessError on non-zero exit
                    )
                    
                    # Check if output file was actually created and has content
                    if not Path(compression_output_file).exists():
                        return (file, False, f"Output file not created: {compression_output_file}", False)
                    elif Path(compression_output_file).stat().st_size == 0:
                        # If empty, there might be an issue - log stderr if available
                        error_msg = f"Output file is empty. Stderr: {result.stderr}" if result.stderr else "Output file is empty"
                        return (file, False, error_msg, False)
                    
                    # Check for unrecoverable errors in the output file
                    try:
                        with open(compression_output_file, 'r') as f:
                            output_content = f.read()
                            if "Line too big" in output_content or "Footer is full" in output_content:
                                # These are unrecoverable errors - don't retry
                                error_msg = "Unrecoverable error: "
                                if "Line too big" in output_content:
                                    error_msg += "Line too big"
                                if "Footer is full" in output_content:
                                    if "Line too big" in output_content:
                                        error_msg += " and Footer is full"
                                    else:
                                        error_msg += "Footer is full"
                                return (file, False, error_msg, True)  # Mark as unrecoverable
                    except Exception:
                        # If we can't read the file, continue normally
                        pass
                    
                    return (file, True, None, False)
                except subprocess.CalledProcessError as e:
                    error_details = f"Process exited with code {e.returncode}"
                    if e.stderr:
                        error_details += f". Stderr: {e.stderr}"
                    return (file, False, error_details, False)
                except Exception as e:
                    return (file, False, str(e), False)
    
    return (file, False, "Not a compressible file type", False)

def robust_parallel_compress(files_to_compress, num_workers=None):
    """
    Robustly compress files in parallel with retry logic and memory management.
    Returns list of (file, success, error_msg) tuples.
    """
    if num_workers is None:
        num_workers = max(1, cpu_count() - 1)  # Leave one core free for system tasks
    
    results = []
    failed_files = []  # List of (file, retry_count, is_unrecoverable) tuples
    skipped_files = []
    max_retries = 3
    
    # First, separate object type .stores files which should be skipped
    files_to_actually_compress = []
    for file in files_to_compress:
        if file.name.endswith('.stores'):
            parts = file.name.replace('.stores', '').split('_')
            if len(parts) >= 4 and parts[2] == 'object':
                skipped_files.append(file)
                results.append((file, False, "Buffers containing objects are not compressible"))
            else:
                files_to_actually_compress.append(file)
        else:
            files_to_actually_compress.append(file)
    
    # Report skipped files immediately
    if skipped_files:
        print(f"[compress] Skipped {len(skipped_files)} object type .stores files (not compressible)")
    
    # If no files to actually compress, return early
    if not files_to_actually_compress:
        return results
    
    # First attempt with multiprocessing pool
    print(f"[compress] Processing {len(files_to_actually_compress)} files using {num_workers} workers")
    
    # Also log to external file
    status_log = Path("/tmp/memlog_parser_status.log")
    with open(status_log, "a") as log:
        log.write(f"[compress] Starting compression of {len(files_to_actually_compress)} files with {num_workers} workers\n")
        log.write(f"[compress] Skipped {len(skipped_files)} object type .stores files\n")
        log.write(f"[compress] Initial memory usage: {get_memory_percent():.1f}%\n")
    
    processed_count = 0
    expected_count = len(files_to_actually_compress)
    
    try:
        # Use spawn context for better memory isolation
        ctx = get_context('spawn')
        
        # Process in smaller chunks to avoid overwhelming memory
        chunk_size = max(1, len(files_to_actually_compress) // (num_workers * 4))
        
        with ctx.Pool(processes=num_workers, maxtasksperchild=10) as pool:
            # Use apply_async with timeout for better control
            async_results = []
            for file in files_to_actually_compress:
                async_results.append((file, pool.apply_async(compress_file, (file,))))
            
            # Monitor results without blocking timeout
            pool.close()  # Stop accepting new tasks
            
            # Monitor completion with periodic checks
            completed = []
            start_time = time.time()
            last_log_time = start_time
            
            while len(completed) < len(async_results):
                time.sleep(30)  # Check every 30 seconds
                current_time = time.time()
                
                # Check which tasks are done
                newly_completed = []
                for idx, (file, async_result) in enumerate(async_results):
                    if idx not in completed:
                        if async_result.ready():
                            try:
                                result = async_result.get(timeout=1)  # Should be immediate since it's ready
                                # result is now (file, success, error_msg, is_unrecoverable)
                                if result[1]:  # Success
                                    results.append(result[:3])  # Only keep first 3 elements for results
                                else:
                                    # Check if it's unrecoverable
                                    is_unrecoverable = result[3] if len(result) > 3 else False
                                    if is_unrecoverable:
                                        # Don't add to failed_files for retry, add directly to results
                                        results.append(result[:3])
                                        print(f"[compress] Unrecoverable error for {file}: {result[2]}")
                                    else:
                                        failed_files.append((result[0], 0, False))
                                newly_completed.append(idx)
                                processed_count += 1
                            except Exception as e:
                                # Worker was killed
                                error_msg = f"Worker killed: {str(e)}"
                                print(f"[compress] {error_msg} for {file}")
                                with open(status_log, "a") as log:
                                    log.write(f"[compress] WORKER KILLED: {file} - {error_msg}\n")
                                failed_files.append((file, 0, False))  # Not unrecoverable, can retry
                                newly_completed.append(idx)
                                processed_count += 1
                
                completed.extend(newly_completed)
                
                # Log progress every 5 minutes
                if current_time - last_log_time > 300:
                    mem_percent = get_memory_percent()
                    elapsed_hours = (current_time - start_time) / 3600
                    success_count = len(results)
                    failure_count = len(failed_files)
                    with open(status_log, "a") as log:
                        log.write(f"[compress] Progress: {len(completed)}/{expected_count} completed, "
                                f"Success: {success_count}, Failures: {failure_count}, "
                                f"Elapsed: {elapsed_hours:.1f}h, Memory: {mem_percent:.1f}%\n")
                        if newly_completed:
                            log.write(f"[compress] Recently completed: {len(newly_completed)} files\n")
                    last_log_time = current_time
                    
                    # Check for high memory
                    if mem_percent > 95:
                        print(f"[compress] CRITICAL: Memory at {mem_percent:.1f}%!")
                        with open(status_log, "a") as log:
                            log.write(f"[compress] CRITICAL MEMORY: {mem_percent:.1f}%\n")
            
            pool.join()  # Wait for all workers to finish
    
    except Exception as e:
        error_msg = f"Pool processing failed: {e}"
        print(f"[compress] {error_msg}. Falling back to sequential processing.")
        with open(status_log, "a") as log:
            log.write(f"[compress] POOL FAILURE: {error_msg}\n")
            log.write(f"[compress] Processed {processed_count} out of {expected_count} files before failure\n")
        
        # Add all unprocessed files to failed list (excluding already skipped object type .stores files)
        processed_files = {r[0] for r in results}
        processed_files.update({f for f, _, _ in failed_files})
        for f in files_to_actually_compress:
            if f not in processed_files:
                failed_files.append((f, 0, False))  # Not unrecoverable, can retry
    
    # Retry failed files with reduced parallelism or sequentially
    while failed_files and any(retry_count < max_retries and not is_unrec for _, retry_count, is_unrec in failed_files):
        print(f"[compress] Retrying {len(failed_files)} failed files...")
        new_failed = []
        
        for file, retry_count, is_unrecoverable in failed_files:
            # Skip object type .stores files - they should never be in failed_files but double check
            if file.name.endswith('.stores'):
                parts = file.name.replace('.stores', '').split('_')
                if len(parts) >= 4 and parts[2] == 'object':
                    results.append((file, False, "Buffers containing objects are not compressible"))
                    continue
            
            # Skip unrecoverable errors
            if is_unrecoverable:
                results.append((file, False, f"Unrecoverable error - no retry attempted"))
                continue
                
            if retry_count >= max_retries:
                # Max retries reached, mark as permanently failed
                results.append((file, False, f"Failed after {max_retries} retries"))
                continue
            
            # Check memory before attempting
            mem_percent = get_memory_percent()
            if mem_percent > 85:
                print(f"[compress] Memory at {mem_percent:.1f}%, waiting before retry...")
                time.sleep(5)
            
            # Try sequential processing for retries
            try:
                result = compress_file(file)
                # result is now (file, success, error_msg, is_unrecoverable)
                if result[1]:  # Success
                    results.append(result[:3])  # Only keep first 3 elements
                    print(f"[compress] Successfully compressed {file} on retry {retry_count + 1}")
                else:
                    # Check if the new failure is unrecoverable
                    is_unrecoverable_now = result[3] if len(result) > 3 else False
                    if is_unrecoverable_now:
                        # Don't retry unrecoverable errors
                        results.append(result[:3])
                        print(f"[compress] Unrecoverable error encountered on retry for {file}: {result[2]}")
                    else:
                        # Check if it's an object type file
                        is_object = False
                        if file.name.endswith('.stores'):
                            parts = file.name.replace('.stores', '').split('_')
                            if len(parts) >= 4 and parts[2] == 'object':
                                is_object = True
                        if not is_object:
                            new_failed.append((file, retry_count + 1, False))
                        else:
                            results.append((file, False, "Buffers containing objects are not compressible"))
            except Exception as e:
                print(f"[compress] Retry failed for {file}: {e}")
                # Don't retry object type .stores files
                is_object = False
                if file.name.endswith('.stores'):
                    parts = file.name.replace('.stores', '').split('_')
                    if len(parts) >= 4 and parts[2] == 'object':
                        is_object = True
                if not is_object:
                    new_failed.append((file, retry_count + 1, False))
                else:
                    results.append((file, False, "Buffers containing objects are not compressible"))
        
        failed_files = new_failed
    
    # Final report of permanently failed files
    for file, _, is_unrecoverable in failed_files:
        if is_unrecoverable:
            results.append((file, False, "Unrecoverable error - no retry attempted"))
        else:
            results.append((file, False, "Permanent failure after all retries"))
    
    return results

# -------------------------------------------------------
if __name__ == "__main__":
    import argparse, subprocess, sys

    parser = argparse.ArgumentParser(description="Parse Valgrind logs; ignore ALLOCs without STOREs.")
    parser.add_argument("logfile", nargs='?', help="Ruta al fichero .log a procesar")
    parser.add_argument("--compress", default=True, action='store_true', help="Compress parsed files (default: True)")
    parser.add_argument("--parsed-dir", default=None, help="Path to an existing parsed directory to process (skips parsing)")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: auto)")
    parser.add_argument("--sequential", action='store_true', help="Force sequential processing (no parallelism)")
    args = parser.parse_args()
    
    if args.parsed_dir:
        # Use existing parsed directory
        out_dir = Path(args.parsed_dir)
        if not out_dir.is_dir():
            print(f"[parse_log] Parsed directory not found: {out_dir}")
            sys.exit(1)
    else:
        # Parse log file
        if not args.logfile:
            print("[parse_log] Error: logfile is required when --parsed-dir is not provided")
            sys.exit(1)
        log_path = Path(args.logfile)
        if not log_path.is_file():
            print(f"[parse_log] File not found: {log_path}, skipping compression")
            sys.exit(0)

        out_dir = parse_log(args.logfile)
        # Compress each parsed file in parallel
        if args.compress:
            # Collect all files to process
            files_to_compress = [f for f in out_dir.iterdir() if f.is_file()]
            
            if files_to_compress:
                # Check if sequential processing is requested
                if args.sequential:
                    print(f"[compress] Sequential processing of {len(files_to_compress)} files")
                    results = []
                    for idx, file in enumerate(files_to_compress):
                        if (idx + 1) % 10 == 0:
                            print(f"[compress] Progress: {idx + 1}/{len(files_to_compress)}")
                        try:
                            result = compress_file(file)
                            # result is now (file, success, error_msg, is_unrecoverable)
                            results.append(result[:3])  # Only keep first 3 elements for compatibility
                        except Exception as e:
                            results.append((file, False, str(e)))
                else:
                    # Use robust compression with automatic retry and memory management
                    num_workers = args.workers if args.workers else None
                    results = robust_parallel_compress(files_to_compress, num_workers=num_workers)
                
                # Report results
                critical_failures = []
                for file, success, error_msg in results:
                    if not success:
                        is_object = False
                        if file.name.endswith('.stores'):
                            parts = file.name.replace('.stores', '').split('_')
                            if len(parts) >= 4 and parts[2] == 'object':
                                is_object = True
                        if is_object:
                            print(f"[compress_skip] {file}: {error_msg}", file=sys.stderr)
                        elif error_msg and error_msg != "Not a compressible file type":
                            print(f"[compress_error] {file}: {error_msg}", file=sys.stderr)
                            if "Permanent failure" in error_msg or "Failed after" in error_msg:
                                critical_failures.append(file)
                
                # Report critical failures summary
                if critical_failures:
                    print(f"\n[CRITICAL] {len(critical_failures)} files failed compression after all retries:", file=sys.stderr)
                    
                    # Also write to external log file
                    status_log = Path("/tmp/memlog_parser_status.log")
                    with open(status_log, "a") as log:
                        log.write(f"\n[CRITICAL] {len(critical_failures)} files failed after all retries:\n")
                        for f in critical_failures:
                            log.write(f"  - {f}\n")
                    
                    for f in critical_failures[:10]:  # Show first 10
                        print(f"  - {f}", file=sys.stderr)
                    if len(critical_failures) > 10:
                        print(f"  ... and {len(critical_failures) - 10} more", file=sys.stderr)
                    print("\nThese files MUST be processed manually or the analysis will be incomplete!", file=sys.stderr)
    # Process compression after all subprocesses complete
    process_compression(out_dir)
    sys.exit(0)
