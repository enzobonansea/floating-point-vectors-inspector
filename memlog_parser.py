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
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm

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
        "stores",
        "aligned32",
        "aligned64",
        "base_core",
    )

    def __init__(self, start: int, size: int, base_core: str):
        self.start = start
        self.size = size
        self.end = start + size
        self.stores = []  # List of (addr_hex, value_hex, offset) tuples
        self.aligned32 = True
        self.aligned64 = True
        self.base_core = base_core

    # ------------------------------------------------------------------
    def write_store(self, addr_hex: str, value_hex: str) -> None:
        addr = int(addr_hex, 16)
        offset = addr - self.start
        self.stores.append((addr_hex.lower(), value_hex.lower(), offset))
        if self.aligned32 and offset % 4 != 0:
            self.aligned32 = False
        if self.aligned64 and offset % 8 != 0:
            self.aligned64 = False

    # ------------------------------------------------------------------
    def close_and_finalize(self, out_dir: Path) -> None:
        if not self.stores:
            # Ninguna STORE ⇒ no crear archivo
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
        
        # Write all stores to the final file
        with target.open("w", encoding="utf-8") as fh:
            for addr_hex, value_hex, offset in self.stores:
                fh.write(f"0x{addr_hex} 0x{value_hex} {offset}\n")

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

    file_size = log_path.stat().st_size
    with tqdm(total=file_size, desc="Parsing log", unit="B", unit_scale=True) as pbar, log_path.open("r", encoding="utf-8", errors="ignore") as fh:

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
                        alloc.write_store(addr_hex, value_hex)
                continue

            # ALLOC / FREE delimiters -----------------------------------
            if line.startswith("===ALLOC START==="):
                inside_alloc = True; continue
            if line.startswith("===ALLOC END==="):
                inside_alloc = False; continue
            if line.startswith("===FREE START==="):
                inside_free = True; continue
            if line.startswith("===FREE END==="):
                inside_free = False; continue            # ALLOC header ----------------------------------------------
            if inside_alloc:
                m_alloc = ALLOC_HEADER_RE.match(line)
                if m_alloc:
                    start_hex, size_str = m_alloc.groups()
                    start_int = int(start_hex, 16)
                    size_int = int(size_str)
                    base_core = f"0x{start_hex.lower()}_{size_int}"
                    _add(LiveAlloc(start_int, size_int, base_core))
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
                        alloc.close_and_finalize(out_dir)
                        _remove(alloc)
                continue

    # Finaliza los allocs vivos sin FREE
    for alloc in list(live_list):
        alloc.close_and_finalize(out_dir)
        _remove(alloc)

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
        print("filename,type,block_size,all_zeros,execution_failed,exception,error_type,ulr_miss_qty,size_reduced_percentage,validation_passed,lossless,file_size,partially_compressed_lines,total_lines", file=outfile)

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
            error_type = ""
            partially_compressed_lines = False

            # Leer archivo .compression
            try:
                with open(comp_path, "r") as compfile:
                    output = compfile.read()
                    # Check for specific error patterns first
                    if "LineTooBig" in output:
                        error_type = "LineTooBig"
                        execution_failed = True
                        exception = "Line too big for compression"
                    elif "FooterFull" in output:
                        error_type = "FooterFull"
                        execution_failed = True
                        exception = "Compression footer full"
                        
                    output = output.splitlines()
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
                error_type = type(e).__name__

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
            print(f"{fname},{ftype},{block_size},{all_zeros},{execution_failed},{exception},{error_type},{ulr},{size_reduced_percentage},{validation_passed},{lossless},{file_size},{partially_compressed_lines},{total_lines}", file=outfile)

    with open(summary_file, "w") as summary:
        print("compression_files,successful_compressions,total_block_size,total_compressed_size", file=summary)
        print(f"{total_compression_files},{successful_compressions},{total_block_size},{int(total_compressed_size)}", file=summary)

    return analyzed_file
        


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
        # Compress each parsed file
        if args.compress:
            for file in out_dir.iterdir():
                if file.is_file():
                    with open(f"{file}.compression", "w", encoding="utf-8") as fh:
                        try:
                            subprocess.run(["/usr/mmu_compressor", str(file)], stdout=fh, stderr=subprocess.DEVNULL)
                        except Exception as e:
                            print(f"[compress_error] {{file}}: {{e}}", file=sys.stderr)
    process_compression(out_dir)
    sys.exit(0)
