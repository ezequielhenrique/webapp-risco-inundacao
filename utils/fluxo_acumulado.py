from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import numpy as np
import rasterio


def normalize_nodata_for_whitebox(input_tif: str, output_tif: str, nodata_value: float = -9999.0) -> float:
    """Garante que o raster tenha um NoData numérico (Whitebox não lida bem com NaN)."""

    with rasterio.open(input_tif) as src:
        profile = src.profile.copy()
        data = src.read(1)
        src_nodata = src.nodata

    if src_nodata is not None and not (isinstance(src_nodata, float) and np.isnan(src_nodata)):
        if not np.isnan(data).any():
            profile.update(nodata=src_nodata)
            with rasterio.open(output_tif, "w", **profile) as dst:
                dst.write(data, 1)
            return float(src_nodata)

    data_out = data.astype(np.float32, copy=False)
    data_out = np.where(np.isnan(data_out), nodata_value, data_out)

    profile.update(dtype=rasterio.float32, nodata=nodata_value)
    with rasterio.open(output_tif, "w", **profile) as dst:
        dst.write(data_out.astype(rasterio.float32), 1)

    return float(nodata_value)


def realizar_analise_de_fluxo(cidade: str):
    """Calcula fluxo acumulado (D8) a partir do MDE já alinhado em outputs/mde/.

    Saída: outputs/fluxo_acumulado/fluxo_acumulado_<cidade>.tif
    """

    try:
        from whitebox.whitebox_tools import WhiteboxTools
    except Exception as e:
        raise RuntimeError(
            "Dependência ausente: 'whitebox'. Instale com `pip install whitebox` (ou requirements.txt)."
        ) from e

    out_dir = Path("outputs/fluxo_acumulado")
    out_dir.mkdir(parents=True, exist_ok=True)
    mde_in = Path(f"outputs/mde/mde_{cidade}.tif")
    out_acc = out_dir / f"fluxo_acumulado_{cidade}.tif"

    # Rodar o Whitebox em um caminho ASCII (ex.: /tmp) para evitar falhas com caminhos Unicode
    # (Google Drive / nomes com acentos). Depois copiamos a saída para o workspace.
    with tempfile.TemporaryDirectory(prefix=f"wbt_fluxo_{cidade}_") as tmp:
        tmp_dir = Path(tmp)
        tmp_mde_in = tmp_dir / "mde_in.tif"
        tmp_mde_nodata = tmp_dir / "mde_nodata.tif"
        tmp_mde_filled = tmp_dir / "mde_filled.tif"
        tmp_out_acc = tmp_dir / "fluxo_acumulado.tif"

        # Copiar o MDE já alinhado (10m) para o diretório temporário
        shutil.copyfile(mde_in, tmp_mde_in)

        normalize_nodata_for_whitebox(str(tmp_mde_in), str(tmp_mde_nodata), nodata_value=-9999.0)

        wbt = WhiteboxTools()
        wbt.verbose = False

        # Importante: o executável do Whitebox costuma ficar dentro do site-packages em um caminho
        # com acentos (ex.: Google Drive). Em macOS, isso pode causar falhas silenciosas.
        # Copiamos o binário para o tmp_dir (ASCII) e apontamos o exe_path para lá.
        try:
            src_exe_dir = Path(str(wbt.exe_path))
            src_exe = src_exe_dir / "whitebox_tools"
            dst_exe = tmp_dir / "whitebox_tools"
            if src_exe.exists() and not dst_exe.exists():
                shutil.copyfile(src_exe, dst_exe)
                dst_exe.chmod(0o755)
            # WhiteboxTools usa exe_path como diretório onde está o binário.
            if dst_exe.exists():
                wbt.exe_path = str(tmp_dir)
        except Exception:
            # Se falhar, seguimos com o exe_path padrão.
            pass

        wbt.work_dir = str(tmp_dir)

        # 1) Preencher depressões
        # Obs: alguns builds do Whitebox são mais confiáveis com caminhos relativos ao work_dir.
        # Preferir caminhos absolutos para evitar escrita fora do tmp_dir.
        ret_fill = wbt.fill_depressions(dem=str(tmp_mde_nodata), output=str(tmp_mde_filled), fix_flats=True)

        # Fallback: alguns builds podem ignorar caminhos absolutos e escrever no work_dir.
        if not tmp_mde_filled.exists():
            alt = tmp_dir / "mde_filled.tif"
            if alt.exists() and alt != tmp_mde_filled:
                shutil.move(str(alt), str(tmp_mde_filled))

        if not tmp_mde_filled.exists():
            raise RuntimeError(
                "Falha ao preencher depressões (Whitebox). O arquivo não foi criado em: "
                + str(tmp_mde_filled)
                + f" (ret={ret_fill}). exe_path={getattr(wbt, 'exe_path', '')} work_dir={getattr(wbt, 'work_dir', '')}"
            )

        # 2) Fluxo acumulado (em número de células)
        ret_acc = wbt.d8_flow_accumulation(i=str(tmp_mde_filled), output=str(tmp_out_acc), out_type="cells")

        if not tmp_out_acc.exists():
            raise RuntimeError(
                "Falha ao gerar fluxo acumulado (Whitebox). O arquivo de saída não foi criado em: "
                + str(tmp_out_acc)
                + f" (ret={ret_acc})"
            )

        # Copiar saída para o workspace (sobrescreve)
        out_acc.parent.mkdir(parents=True, exist_ok=True)
        try:
            if out_acc.exists():
                out_acc.unlink()
        except Exception:
            pass
        shutil.copyfile(tmp_out_acc, out_acc)

    # Validar saída: deve manter exatamente o mesmo grid do MDE de entrada (outputs/mde).
    if not out_acc.exists():
        raise RuntimeError(
            "Falha ao gerar fluxo acumulado (Whitebox). O arquivo de saída não foi criado: " + str(out_acc)
        )

    with rasterio.open(mde_in) as ref, rasterio.open(out_acc) as out:
        if ref.crs != out.crs or ref.transform != out.transform or ref.width != out.width or ref.height != out.height:
            raise RuntimeError(
                "Fluxo acumulado gerado com grid diferente do MDE (provável arquivo antigo ou falha do Whitebox). "
                f"MDE: {ref.width}x{ref.height}, Fluxo: {out.width}x{out.height}. "
                "Tente rodar novamente; se persistir, verifique o WhiteboxTools e apague outputs/fluxo_acumulado/*.tif."
            )
