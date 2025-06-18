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

# -------------------------------------------------------
if __name__ == "__main__":
    import argparse, subprocess, sys

    parser = argparse.ArgumentParser(description="Parse Valgrind logs; ignore ALLOCs without STOREs.")
    parser.add_argument("logfile", help="Ruta al fichero .log a procesar")
    args = parser.parse_args()
    log_path = Path(args.logfile)
    if not log_path.is_file():
        print(f"[parse_log] File not found: {log_path}, skipping compression")
        sys.exit(0)

    out_dir = parse_log(args.logfile)
    # Compress each parsed file
    for file in out_dir.iterdir():
        if file.is_file():
            with open(f"{file}.compression", "w", encoding="utf-8") as fh:
                try:
                    subprocess.run(["/usr/mmu_compressor", str(file)], stdout=fh, stderr=subprocess.DEVNULL)
                except Exception as e:
                    print(f"[compress_error] {{file}}: {{e}}", file=sys.stderr)
    sys.exit(0)
