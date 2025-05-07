#!/usr/bin/env python3
"""parse_valgrind_log.py – versión con control de FREE

*Lee el log una sola vez* y, para cada ciclo **ALLOC → … → FREE**, genera un fichero
`0x<start>_<size>_<sufijo>` que contiene *solo* las STORE ocurridas *antes* de su
FREE correspondiente.

Formato de línea en cada fichero de salida:
```
0x<address_hex> 0x<value_hex> <offset_dec>
```
`offset_dec = address - start` (decimal).

### Sufijos de alineamiento
* `_dist64` — todas las STORE están alineadas a 64 bytes.
* `_dist32` — alineadas a 32 bytes, pero no 64.
* `_distVar` — hay offsets no múltiplos de 32.

### Cómo funciona
1. **Un solo escaneo (streaming)** con barra de progreso `tqdm`.
2. Mantiene un registro de *allocaciones vivas*; al encontrar `FREE`,
   cierra/renombra su fichero según alineamiento y la saca de la lista viva.
3. Cada STORE se dirige al bloque vivo cuyo rango contiene la dirección.

Dependencias mínimas: Python ≥ 3.8 y (opcional) `tqdm`.
"""
from __future__ import annotations

import bisect
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, TextIO

try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # barra muda si no hay tqdm
    def tqdm(iterable=None, *args, **kwargs):  # type: ignore
        return iterable if iterable is not None else (lambda x: x)

# ---------------- Expresiones regulares ----------------
ALLOC_HEADER_RE = re.compile(r"^Start\s+0x([0-9a-fA-F]+),\s+size\s+(\d+)")
STORE_RE = re.compile(r"^0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)")

# -------------------------------------------------------

class LiveAlloc:
    """Representa un ALLOC vivo mientras parseamos."""
    __slots__ = ("start", "size", "end", "fh", "aligned32", "aligned64", "base_core")

    def __init__(self, start: int, size: int, fh: TextIO, base_core: str):
        self.start = start
        self.size = size
        self.end = start + size
        self.fh = fh
        self.aligned32 = True
        self.aligned64 = True
        self.base_core = base_core  # ej. 0x4b50040_4096

    def write_store(self, addr_hex: str, value_hex: str) -> None:
        addr = int(addr_hex, 16)
        offset = addr - self.start
        self.fh.write(f"0x{addr_hex.lower()} 0x{value_hex.lower()} {offset}\n")
        if self.aligned32 and offset % 32 != 0:
            self.aligned32 = False
        if self.aligned64 and offset % 64 != 0:
            self.aligned64 = False

    def close_and_rename(self, out_dir: Path) -> None:
        self.fh.close()
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
        (out_dir / self.fh.name).rename(target)

# -------------------------------------------------------

def parse_log(log_path: str | os.PathLike) -> Path:
    """Parses a giant Valgrind log streaming; splits STOREs before their FREE."""
    log_path = Path(log_path)
    if not log_path.is_file():
        raise FileNotFoundError(log_path)

    out_dir = log_path.with_suffix(log_path.suffix + ".parsed")
    out_dir.mkdir(exist_ok=True)

    # Estructuras para allocs vivos
    # Diccionario ordenado por start → lista LIFO de LiveAlloc (por si se reutiliza misma dirección)
    live_allocs: Dict[int, List[LiveAlloc]] = defaultdict(list)
    # Lista ordenada de (start, LiveAlloc) para búsqueda binaria rápida
    starts_sorted: List[int] = []  # mantiene misma longitud que live_list
    live_list: List[LiveAlloc] = []

    def _add_live_alloc(alloc: LiveAlloc):
        # Insertamos manteniendo starts_sorted ordenado
        idx = bisect.bisect_left(starts_sorted, alloc.start)
        starts_sorted.insert(idx, alloc.start)
        live_list.insert(idx, alloc)
        live_allocs[alloc.start].append(alloc)

    def _remove_live_alloc(alloc: LiveAlloc):
        idx = live_list.index(alloc)
        starts_sorted.pop(idx)
        live_list.pop(idx)
        live_allocs[alloc.start].pop()  # LIFO

    file_size = log_path.stat().st_size
    with tqdm(total=file_size, desc="Parsing log", unit="B", unit_scale=True) as pbar:
        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            inside_alloc = False
            inside_free = False
            pending_alloc_start: Tuple[str, str] | None = None  # (start_hex, size_str)
            pending_free_start: Tuple[str, str] | None = None
            seq_counter = 0  # asegura nombres únicos

            for line in fh:
                pbar.update(len(line))

                # ---------- STORE ----------
                m_store = STORE_RE.match(line)
                if m_store:
                    addr_hex, value_hex = m_store.groups()
                    addr_int = int(addr_hex, 16)
                    # búsqueda binaria en starts_sorted
                    pos = bisect.bisect_right(starts_sorted, addr_int) - 1
                    if pos >= 0:
                        alloc = live_list[pos]
                        if addr_int <= alloc.end:
                            alloc.write_store(addr_hex, value_hex)
                    continue  # línea procesada

                # ---------- ALLOC / FREE delimiters ----------
                if line.startswith("===ALLOC START==="):
                    inside_alloc = True
                    continue
                if line.startswith("===ALLOC END==="):
                    inside_alloc = False
                    continue
                if line.startswith("===FREE START==="):
                    inside_free = True
                    continue
                if line.startswith("===FREE END==="):
                    inside_free = False
                    continue

                # ---------- ALLOC header ----------
                if inside_alloc:
                    m_alloc = ALLOC_HEADER_RE.match(line)
                    if m_alloc:
                        start_hex, size_str = m_alloc.groups()
                        start_int = int(start_hex, 16)
                        size_int = int(size_str)
                        base_core = f"0x{start_hex.lower()}_{size_int}"
                        # Asegura nombre único añadiendo un contador secuencial
                        seq_counter += 1
                        tmp_name = f"{base_core}__tmp{seq_counter}"  # se renombrará al cerrar
                        fh_out = (out_dir / tmp_name).open("w", encoding="utf-8", buffering=1)
                        alloc = LiveAlloc(start_int, size_int, fh_out, base_core)
                        _add_live_alloc(alloc)
                    continue

                # ---------- FREE header ----------
                if inside_free:
                    m_free = ALLOC_HEADER_RE.match(line)  # mismo patrón que ALLOC header
                    if m_free:
                        start_hex, size_str = m_free.groups()
                        start_int = int(start_hex, 16)
                        stack = live_allocs.get(start_int)
                        if stack:
                            alloc = stack[-1]  # LIFO: la más reciente
                            alloc.close_and_rename(out_dir)
                            _remove_live_alloc(alloc)
                    continue

    # Cierra las allocs que quedaron vivas al final (no freed)
    for alloc in list(live_list):
        alloc.close_and_rename(out_dir)
        _remove_live_alloc(alloc)

    print(f"[parse_log] Terminado. Ficheros en: {out_dir}")
    return out_dir

# -------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse Valgrind logs, segment STOREs by live ALLOC blocks (until FREE).")
    parser.add_argument("logfile", help="Ruta al fichero .log a procesar")
    args = parser.parse_args()

    parse_log(args.logfile)
