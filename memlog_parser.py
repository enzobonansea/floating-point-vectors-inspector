#!/usr/bin/env python3
"""parse_valgrind_log.py

Procesa un fichero .log gigantesco con formato Valgrind (headers, ALLOC, STORE, FREE
intercalados) y genera una carpeta `<log>.parsed` que contiene **un fichero por
ALLOC**.  El nombre final de cada fichero es:

```
0x<start_hex>_<size>_<sufijo>
```

* `<start_hex>`  – dirección de inicio (hex).
* `<size>`       – tamaño del bloque en bytes.
* `<sufijo>`     – uno de:
  * `_dist64`  → todas las STORE cumplen `(addr‑start) % 64 == 0`.
  * `_dist32`  → todas las STORE cumplen `(addr‑start) % 32 == 0` (pero NO todas a 64).
  * `_distVar` → no se cumple el alineamiento a 32 para, al menos, una STORE.

Vistas las dimensiones del fichero, el script se ejecuta **en streaming** y usa
`tqdm` para mostrar progreso en cada una de las dos pasadas:

1. **Pass 1/2** – localiza bloques ALLOC y registra sus rangos.
2. **Pass 2/2** – clasifica cada línea STORE en su ALLOC mediante búsqueda
   binaria y calcula los alineamientos 32/64.

Si `tqdm` no está instalado, el script funciona sin barras.

Uso
----
```bash
python parse_valgrind_log.py /ruta/al/fichero.log
```
Desde otro código:
```python
from parse_valgrind_log import parse_log
parse_log("/ruta/al/fichero.log")
```

Requiere Python ≥3.8.
"""
from __future__ import annotations

import bisect
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, TextIO

try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # stub sin funcionalidad
    def tqdm(iterable=None, *args, **kwargs):  # type: ignore
        return iterable if iterable is not None else (lambda x: x)

# ----------------------- Expresiones regulares reutilizables ------------------------------
ALLOC_HEADER_RE = re.compile(r"^Start\s+0x([0-9a-fA-F]+),\s+size\s+(\d+)")
STORE_RE = re.compile(r"^0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)")

# ------------------------------------------------------------------------------------------

def _collect_allocs(log_path: Path) -> List[Tuple[int, int, str]]:
    """Primera pasada – devuelve lista `(start, end, base_filename)` ordenada por inicio."""
    allocs: List[Tuple[int, int, str]] = []
    inside_alloc = False
    file_size = log_path.stat().st_size

    with tqdm(total=file_size, desc="Pass 1/2: Detecting ALLOCs", unit="B", unit_scale=True) as pbar:
        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                pbar.update(len(line))

                if line.startswith("===ALLOC START==="):
                    inside_alloc = True
                    continue

                if inside_alloc:
                    m = ALLOC_HEADER_RE.match(line)
                    if m:
                        start_hex, size_str = m.groups()
                        start = int(start_hex, 16)
                        size = int(size_str)
                        end = start + size  # intervalo inclusivo
                        base_name = f"0x{start_hex.lower()}_{size}"
                        allocs.append((start, end, base_name))
                        continue

                    if line.startswith("===ALLOC END==="):
                        inside_alloc = False

    allocs.sort(key=lambda t: t[0])
    return allocs


def _write_stores(
    log_path: Path,
    allocs: List[Tuple[int, int, str]],
    output_dir: Path,
    aligned32: List[bool],
    aligned64: List[bool],
) -> None:
    """Segunda pasada: reparte STOREs y actualiza alineamientos."""
    if not allocs:
        return

    starts = [start for start, _end, _bn in allocs]
    open_files: Dict[str, TextIO] = {}

    def _fh_for(filename: str) -> TextIO:
        fh = open_files.get(filename)
        if fh is None:
            fh = (output_dir / filename).open("a", encoding="utf-8")
            open_files[filename] = fh
        return fh

    file_size = log_path.stat().st_size
    with tqdm(total=file_size, desc="Pass 2/2: Classifying STOREs", unit="B", unit_scale=True) as pbar:
        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                pbar.update(len(line))
                m = STORE_RE.match(line)
                if not m:
                    continue

                addr = int(m.group(1), 16)
                idx = bisect.bisect_right(starts, addr) - 1
                if idx < 0:
                    continue  # antes del primer ALLOC

                start, end, base_name = allocs[idx]
                if addr <= end:
                    _fh_for(base_name).write(line)
                    # actualizamos flags de alineamiento
                    offset = addr - start
                    if aligned32[idx] and offset % 4 != 0:
                        aligned32[idx] = False
                    if aligned64[idx] and offset % 8 != 0:
                        aligned64[idx] = False

    for fh in open_files.values():
        fh.close()


# ------------------------------------------------------------------------------------------

def parse_log(log_path: str | os.PathLike, *, encoding: str = "utf-8") -> Path:
    """Parses a huge Valgrind log and splits STORE lines by ALLOC, adding alignment suffix."""
    log_path = Path(log_path)
    if not log_path.is_file():
        raise FileNotFoundError(log_path)

    out_dir = log_path.with_suffix(log_path.suffix + ".parsed")
    out_dir.mkdir(exist_ok=True)

    # ---------------- Primera pasada ------------------------------------------------------
    allocs = _collect_allocs(log_path)
    if not allocs:
        print("[parse_log] No se encontraron bloques ALLOC.")
        return out_dir

    # Creamos ficheros vacíos (por si hay ALLOC sin STORE)
    for _start, _end, fname in allocs:
        (out_dir / fname).touch(exist_ok=True)

    # ---------------- Segunda pasada ------------------------------------------------------
    aligned32 = [True] * len(allocs)
    aligned64 = [True] * len(allocs)
    _write_stores(log_path, allocs, out_dir, aligned32, aligned64)

    # ---------------- Renombrado según alineamiento ---------------------------------------
    for (start, end, base_name), a32, a64 in zip(allocs, aligned32, aligned64):
        old = out_dir / base_name
        if not old.exists():
            continue  # debería existir, pero por si acaso

        suffix = "_distVar"
        if a32:
            suffix = "_dist64" if a64 else "_dist32"
        new = out_dir / f"{base_name}{suffix}"
        # Evitamos sobrescribir si el nombre destino ya existe (extremadamente raro)
        if new.exists():
            # añadimos un contador incremental
            i = 1
            while (out_dir / f"{base_name}{suffix}.{i}").exists():
                i += 1
            new = out_dir / f"{base_name}{suffix}.{i}"
        old.rename(new)

    print(f"[parse_log] Terminado. Ficheros en: {out_dir}")
    return out_dir


# ------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse giant Valgrind logs, split STORE lines by ALLOC, and label distance patterns.")
    parser.add_argument("logfile", help="Ruta al fichero .log a procesar")
    args = parser.parse_args()

    parse_log(args.logfile)
