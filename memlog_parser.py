#!/usr/bin/env python3
"""parse_valgrind_log.py – ignora ALLOCs sin STORE

Procesa un log Valgrind en streaming y, **solo si un bloque ALLOC recibe al menos
una STORE antes de su FREE**, genera un fichero con formato:
```
0x<start_hex>_<size>_<sufijo>
0x<address_hex> 0x<value_hex> <offset_dec>
```
`<sufijo>` = `_dist64`, `_dist32` o `_distVar` según alineamiento.

En cuanto aparece el FREE, el fichero se cierra y se renombra; si quedó vacío se
elimina.  Dependencias: Python ≥ 3.8 y opcionalmente `tqdm`.
"""
from __future__ import annotations

import bisect
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, TextIO
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from functools import partial

# ---------------- Expresiones regulares ----------------
ALLOC_HEADER_RE = re.compile(r"^Start\s+0x([0-9a-fA-F]+),\s+size\s+(\d+)")
STORE_RE = re.compile(r"^0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)")

# -------------------------------------------------------

class LiveAlloc:
    """Representa un bloque de memoria activo entre ALLOC y FREE."""
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
    )

    def __init__(self, start: int, size: int, base_core: str, out_dir: Path):
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
            # No STOREs ⇒ no file needed
            return
        
        suffix = "_distVar"
        if self.aligned32:
            suffix = "_dist64" if self.aligned64 else "_dist32"
        new_name = f"{self.base_core}{suffix}"
        target = out_dir / new_name
        if target.exists():
            i = 1
            while (out_dir / f"{new_name}.{i}").exists():
                i += 1
            target = out_dir / f"{new_name}.{i}"
        
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
                pos = bisect.bisect_right(starts_sorted, addr_int) - 1
                if pos >= 0:
                    alloc = live_list[pos]
                    if addr_int <= alloc.end:
                        alloc.write_store(addr_hex, value_hex, temp_file)
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
                    _add(LiveAlloc(start_int, size_int, base_core, out_dir))
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

    print(f"[parse_log] Terminado. Ficheros en: {out_dir}")
    return out_dir

# Process parsed files
def process_compression(parsed_dir: str | os.PathLike) -> Path:
    parsed_dir = Path(parsed_dir)
    if not parsed_dir.is_dir():
        raise NotADirectoryError(parsed_dir)

    analyzed_file = parsed_dir / (parsed_dir.name + ".analyzed")
    summary_file = parsed_dir / (parsed_dir.name + ".summary")

    total_compression_files = 0
    successful_compressions = 0
    total_block_size = 0
    total_compressed_size = 0


    with open(analyzed_file, "w") as outfile:
        # Imprimir encabezado CSV
        print("filename,type,block_size,all_zeros,execution_failed,exception,ulr_miss_qty,size_reduced_percentage,validation_passed,lossless,file_size,partially_compressed_lines,total_lines", file=outfile)

        for file in parsed_dir.iterdir():
            if not file.is_file() or file.suffix == ".compression":
                continue

            total_compression_files += 1
            fname = file.name
            dist_path = file
            comp_path = file.with_suffix(file.suffix + ".compression")

            splitted_name = fname.split("_")
            try:
                block_size = int(splitted_name[-2])
            except (IndexError, ValueError):
                block_size = ""
            try:
                ftype = splitted_name[-1]
            except (IndexError, ValueError):
                ftype = ""

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
            size_reduced_vals = []
            validation_passed = False
            lossless = False
            execution_failed = False
            exception = ""
            partially_compressed_lines = False

            # Leer archivo .compression
            try:
                with open(comp_path, "r") as compfile:
                    output = compfile.read().splitlines()
                    for line in output:
                        if "ULR miss qty:" in line:
                            ulr = int(line.split(':')[1].strip())
                        if "Size reduced by" in line:
                            size = float(line.split()[3].replace('%', ''))
                            size_reduced_vals.append(size)
                        if "Validation PASSED: All" in line:
                            validation_passed = True
                        if "Lossless:" in line:
                            if "True" in line:
                                lossless = True
                                successful_compressions += 1
            except Exception as e:
                execution_failed = True
                exception = str(e)

            size_reduced_percentage = ""
            if len(size_reduced_vals) >= 2:
                size_reduced_percentage = size_reduced_vals[1]
                partially_compressed_lines = size_reduced_vals[1] < size_reduced_vals[0]
            elif size_reduced_vals:
                size_reduced_percentage = size_reduced_vals[0]
                partially_compressed_lines = False

            file_size = os.path.getsize(dist_path)

            # Actualización para el .summary
            if isinstance(block_size, int):
                total_block_size += block_size
            if isinstance(size_reduced_percentage, (int, float, str)) and str(size_reduced_percentage).replace('.', '', 1).isdigit():
                reduced = float(size_reduced_percentage)
                total_compressed_size += block_size * (1 - reduced / 100)

            # Imprimir fila CSV
            print(f"{fname},{ftype},{block_size},{all_zeros},{execution_failed},{exception},{ulr},{size_reduced_percentage},{validation_passed},{lossless},{file_size},{partially_compressed_lines},{total_lines}", file=outfile)

    with open(summary_file, "w") as summary:
        print("compression_files,successful_compressions,total_block_size,total_compressed_size", file=summary)
        print(f"{total_compression_files},{successful_compressions},{total_block_size},{int(total_compressed_size)}", file=summary)

    return analyzed_file
        


# Helper function for parallel compression
def compress_file(file: Path) -> tuple:
    """Compress a single file and return result tuple."""
    import subprocess
    import sys
    
    filename = file.name
    # Skip _distVar files (with or without .N suffix) as they are not compressible
    if '_distVar' in filename:
        return (file, False, f"Variable alignment files are not compressible")
    
    # Only compress _dist32 and _dist64 files (with or without .N suffix)
    if '_dist32' in filename or '_dist64' in filename:
        compression_output_file = f"{file}.compression"
        try:
            # Run subprocess with output file argument, capture stderr for debugging
            result = subprocess.run(
                ["/usr/mmu_compressor", str(file), "--output-file", compression_output_file],
                capture_output=True,
                text=True,
                check=True  # Raise CalledProcessError on non-zero exit
            )
            
            # Check if output file was actually created and has content
            if not Path(compression_output_file).exists():
                return (file, False, f"Output file not created: {compression_output_file}")
            elif Path(compression_output_file).stat().st_size == 0:
                # If empty, there might be an issue - log stderr if available
                error_msg = f"Output file is empty. Stderr: {result.stderr}" if result.stderr else "Output file is empty"
                return (file, False, error_msg)
            
            return (file, True, None)
        except subprocess.CalledProcessError as e:
            error_details = f"Process exited with code {e.returncode}"
            if e.stderr:
                error_details += f". Stderr: {e.stderr}"
            return (file, False, error_details)
        except Exception as e:
            return (file, False, str(e))
    
    return (file, False, "Not a compressible file type")

# -------------------------------------------------------
if __name__ == "__main__":
    import argparse, subprocess, sys

    parser = argparse.ArgumentParser(description="Parse Valgrind logs; ignore ALLOCs without STOREs.")
    parser.add_argument("logfile", nargs='?', help="Ruta al fichero .log a procesar")
    parser.add_argument("--compress", default=True, action='store_true', help="Compress parsed files (default: True)")
    parser.add_argument("--parsed-dir", default=None, help="Path to an existing parsed directory to process (skips parsing)")
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
                # Use all but one physical cores for parallel processing
                num_workers = max(1, cpu_count() - 1)
                print(f"[compress] Processing {len(files_to_compress)} files using {num_workers} workers")
                
                # Process files in parallel
                with Pool(processes=num_workers) as pool:
                    results = pool.map(compress_file, files_to_compress)
                
                # Report results
                for file, success, error_msg in results:
                    if not success:
                        if '_distVar' in file.name:
                            print(f"[compress_skip] {file}: {error_msg}", file=sys.stderr)
                        elif error_msg and error_msg != "Not a compressible file type":
                            print(f"[compress_error] {file}: {error_msg}", file=sys.stderr)
    # Process compression after all subprocesses complete
    process_compression(out_dir)
    sys.exit(0)
