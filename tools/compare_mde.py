#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling


@dataclass
class RasterMeta:
    path: str
    exists: bool
    crs: str | None = None
    width: int | None = None
    height: int | None = None
    bounds: tuple[float, float, float, float] | None = None
    res: tuple[float, float] | None = None
    transform: tuple[float, float, float, float, float, float] | None = None
    dtype: str | None = None
    nodata: float | None = None


def _meta(path: Path) -> RasterMeta:
    if not path.exists():
        return RasterMeta(path=str(path), exists=False)

    with rasterio.open(path) as src:
        t = src.transform
        # imprimir só os 6 parâmetros principais para reduzir ruído
        tr6 = (float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f))
        return RasterMeta(
            path=str(path),
            exists=True,
            crs=str(src.crs) if src.crs else None,
            width=int(src.width),
            height=int(src.height),
            bounds=(float(src.bounds.left), float(src.bounds.bottom), float(src.bounds.right), float(src.bounds.top)),
            res=(float(src.res[0]), float(src.res[1])),
            transform=tr6,
            dtype=str(src.dtypes[0]) if src.count >= 1 else None,
            nodata=(float(src.nodata) if src.nodata is not None else None),
        )


def _same_grid(a: Path, b: Path) -> bool:
    with rasterio.open(a) as A, rasterio.open(b) as B:
        return (A.crs == B.crs) and (A.transform == B.transform) and (A.width == B.width) and (A.height == B.height)


def _downsample_read(src: rasterio.io.DatasetReader, max_dim: int = 1200) -> np.ndarray:
    """Lê banda 1 com downsample para reduzir custo/evitar travamentos."""
    h, w = src.height, src.width
    scale = max(h / max_dim, w / max_dim, 1.0)
    out_h = max(1, int(round(h / scale)))
    out_w = max(1, int(round(w / scale)))
    return src.read(1, out_shape=(out_h, out_w), resampling=Resampling.nearest).astype(np.float32, copy=False)


def _diff_stats_quick(a: Path, b: Path, max_dim: int = 1200) -> dict[str, Any] | None:
    """Diferença por amostragem (downsample). Só faz sentido se same_grid=True."""
    with rasterio.open(a) as A, rasterio.open(b) as B:
        arrA = _downsample_read(A, max_dim=max_dim)
        arrB = _downsample_read(B, max_dim=max_dim)

        # Máscara de dados válidos
        valid = np.isfinite(arrA) & np.isfinite(arrB)
        if A.nodata is not None and np.isfinite(A.nodata):
            valid &= arrA != float(A.nodata)
        if B.nodata is not None and np.isfinite(B.nodata):
            valid &= arrB != float(B.nodata)

        n = int(valid.sum())
        if n == 0:
            return None

        d = (arrA[valid] - arrB[valid]).astype(np.float32, copy=False)
        rmse = float(np.sqrt(np.mean(d * d)))
        return {
            "sample_shape": [int(arrA.shape[0]), int(arrA.shape[1])],
            "valid_pixels": n,
            "diff_min": float(d.min()),
            "diff_max": float(d.max()),
            "diff_mean": float(d.mean()),
            "diff_rmse": rmse,
        }


def _print_meta(label: str, m: RasterMeta):
    if not m.exists:
        print(f"  {label}: (não existe) {m.path}")
        return
    b = m.bounds
    print(
        f"  {label}: crs={m.crs} size={m.width}x{m.height} res={m.res} "
        f"bounds=({b[0]:.3f},{b[1]:.3f},{b[2]:.3f},{b[3]:.3f}) nodata={m.nodata} dtype={m.dtype}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compara MDEs do webapp (dados/) com MDEs do projeto zonas-de-risco (outputs/mde/). "
            "Imprime metadados e, quando o grid é idêntico, estatísticas rápidas de diferença (downsample)."
        )
    )
    parser.add_argument(
        "--webapp",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Pasta raiz do webapp (default: .. a partir de tools/)",
    )
    parser.add_argument(
        "--zonas",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "zonas-de-risco-inundacao",
        help="Pasta raiz do projeto zonas-de-risco (default: ../zonas-de-risco-inundacao)",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=1200,
        help="Dimensão máxima (downsample) para cálculo de diferença rápida",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Se informado, salva resultados completos em JSON (sem muita saída no terminal)",
    )

    args = parser.parse_args()

    webapp_root: Path = args.webapp
    zonas_root: Path = args.zonas

    web_dados = webapp_root / "dados"
    zonas_mde = zonas_root / "outputs" / "mde"

    web_mdes = sorted(web_dados.glob("mde_*.tif"))
    if not web_mdes:
        print(f"Nenhum arquivo encontrado em: {web_dados}/mde_*.tif")
        return 2

    results: list[dict[str, Any]] = []

    for web_mde in web_mdes:
        slug = web_mde.stem.replace("mde_", "")  # mde_recife -> recife
        candidates = [
            zonas_mde / f"mde_{slug}.tif",
            zonas_mde / f"mde_{slug}_v1.tif",
            zonas_mde / f"mde_{slug}-v1.tif",
        ]

        # Escolher o primeiro existente; se nenhum existir, ainda reporta
        zonas_mde_path = next((p for p in candidates if p.exists()), candidates[0])

        ma = _meta(web_mde)
        mb = _meta(zonas_mde_path)

        entry: dict[str, Any] = {
            "slug": slug,
            "webapp": asdict(ma),
            "zonas": asdict(mb),
            "same_grid": False,
            "diff_quick": None,
        }

        print("=" * 72)
        print(f"MDE: {slug}")
        _print_meta("webapp", ma)
        _print_meta("zonas ", mb)

        if ma.exists and mb.exists:
            same = _same_grid(web_mde, zonas_mde_path)
            entry["same_grid"] = bool(same)
            print(f"  same_grid: {same}")
            if same:
                dq = _diff_stats_quick(web_mde, zonas_mde_path, max_dim=int(args.max_dim))
                entry["diff_quick"] = dq
                print(f"  diff_quick: {dq}")
            else:
                print("  diff_quick: (pulado; grids diferentes)")
        else:
            print("  same_grid: (pulado; falta arquivo)")

        results.append(entry)

    if args.json_out is not None:
        out = args.json_out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print("=" * 72)
        print(f"Resultados salvos em: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
