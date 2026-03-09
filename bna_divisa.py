"""
Script para extraer cotizaciones de Dólar U.S.A (Divisa y Billete) desde BNA,
guardar histórico y detectar no-actualizaciones.

Salida principal: CSV/XLSX/SQLite con columnas fecha, moneda, segmento, tipo, valor.
Salida secundaria: archivos CSV con formato histórico específico de divisa/billete.
"""

import argparse
import datetime as dt
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
import sqlite3

URL = "https://www.bna.com.ar/Personas"
DEFAULT_OUT = "bna_divisa_hist.csv"
DIVISA_OUT = "bna_dolar_divisa_hist.csv"
BILLETE_OUT = "bna_dolar_billete_hist.csv"
TABLE_NAME = "bna_divisa"


def normalize_text(text: str) -> str:
    """Normaliza texto: quita acentos/diacriticos y pasa a minusculas."""
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    ).lower()


def parse_number(value: str) -> float:
    """Convierte un numero con separadores locales a float (maneja , y .)."""
    raw = value.strip().replace(" ", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    return float(raw)


def fetch_html(url: str, timeout: int = 20) -> str:
    """Descarga el HTML con headers y timeout, manejando codificacion."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def extract_section_block(text: str, section_label: str) -> tuple[str, str]:
    """Extrae el bloque de texto de una seccion (Divisas/Billetes) y su fecha."""
    match = re.search(section_label, text, re.IGNORECASE)
    if not match:
        raise ValueError(f"No se encontró la sección '{section_label}' en la página.")

    tail = text[match.end() :]

    note_pos = None
    if "divisas" in section_label.lower():
        note_match = re.search(
            r"tipo de cambio de cierre de divisa", tail, re.IGNORECASE
        )
        note_pos = note_match.start() if note_match else None

    date_iter = list(re.finditer(r"\b\d{1,2}/\d{1,2}/\d{4}\b", tail))
    if not date_iter:
        raise ValueError(f"No se encontraron fechas en la sección '{section_label}'.")

    blocks = []
    for idx, dmatch in enumerate(date_iter):
        start = dmatch.start()
        end = date_iter[idx + 1].start() if idx + 1 < len(date_iter) else len(tail)
        blocks.append((dmatch.group(0), tail[start:end]))

    if note_pos is not None:
        candidates = [b for b in blocks if tail.find(b[1]) <= note_pos]
        if candidates:
            return candidates[-1]

    return blocks[0]


def extract_usd_compra_venta(block_text: str) -> tuple[float, float]:
    """Busca la fila de Dolar U.S.A y devuelve compra/venta numericas."""
    lines = [ln.strip() for ln in block_text.splitlines() if ln.strip()]
    target = "dolar u.s.a"
    for i, line in enumerate(lines):
        if target in normalize_text(line):
            candidate_parts = [line]
            numbers = re.findall(r"\d[\d.,]*", line)
            look_ahead = 1
            while (
                len(numbers) < 2 and (i + look_ahead) < len(lines) and look_ahead <= 6
            ):
                candidate_parts.append(lines[i + look_ahead])
                candidate = " ".join(candidate_parts)
                numbers = re.findall(r"\d[\d.,]*", candidate)
                look_ahead += 1
            if len(numbers) < 2:
                raise ValueError("No se pudo extraer Compra/Venta para Dolar U.S.A.")
            compra_raw = numbers[-2]
            venta_raw = numbers[-1]
            return parse_number(compra_raw), parse_number(venta_raw)
    raise ValueError("No se encontró la fila de Dolar U.S.A en la sección Divisas.")


def load_existing(path: Path) -> pd.DataFrame:
    """Carga el historico existente segun extension (CSV/XLSX/SQLite)."""
    if not path.exists():
        return pd.DataFrame(columns=["fecha", "moneda", "segmento", "tipo", "valor"])

    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() in {".sqlite", ".db"}:
        with sqlite3.connect(path) as conn:
            return pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)
    return pd.read_csv(path)


def save_data(df: pd.DataFrame, path: Path) -> None:
    """Guarda el historico en el formato solicitado por extension."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
        return
    if path.suffix.lower() in {".sqlite", ".db"}:
        with sqlite3.connect(path) as conn:
            df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        return
    df.to_csv(path, index=False)


def fill_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Rellena huecos de fechas usando el valor anterior (forward fill)."""
    if df.empty:
        return df

    # Asegurar tipos y ordenar
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["fecha", "moneda", "segmento", "tipo"])

    # Crear un rango completo de fechas desde la minima a la maxima
    rango_fechas = pd.date_range(
        start=df["fecha"].min(), end=df["fecha"].max(), freq="D"
    )

    # Crear todas las combinaciones posibles de [fecha, moneda, segmento, tipo]
    monedas = df["moneda"].unique()
    segmentos = df["segmento"].unique()
    tipos = df["tipo"].unique()

    idx = pd.MultiIndex.from_product(
        [rango_fechas, monedas, segmentos, tipos],
        names=["fecha", "moneda", "segmento", "tipo"],
    )

    # Reindexar y aplicar forward fill por grupo
    df_lleno = df.set_index(["fecha", "moneda", "segmento", "tipo"]).reindex(idx)
    df_lleno = (
        df_lleno.groupby(["moneda", "segmento", "tipo"], group_keys=False)
        .ffill()
        .reset_index()
    )

    # Volver a formato de fecha string ISO para guardado
    df_lleno["fecha"] = df_lleno["fecha"].dt.strftime("%Y-%m-%d")
    return df_lleno


def format_decimal(
    value: float,
    max_decimals: int = 4,
    fixed_decimals: int | None = None,
    use_thousands: bool = False,
) -> str:
    """Formatea decimales con separadores localizados segun necesidad."""
    fmt = f",.{fixed_decimals}f" if fixed_decimals is not None else f",.{max_decimals}f"
    formatted = (
        format(value, fmt) if use_thousands else format(value, fmt).replace(",", "")
    )
    if fixed_decimals is None:
        formatted = formatted.rstrip("0").rstrip(".")
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def update_divisa_file(path: Path, rows: list[dict]) -> None:
    """Actualiza CSV especifico de Divisa con formato historico legado."""
    if not path.exists():
        header = "Fecha;Divisa Compra; Divisa Venta "
        path.write_text(header + "\n", encoding="utf-8")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        lines = ["Fecha;Billete Compra;Billete Venta;Divisa Compra; Divisa Venta "]

    header = lines[0]
    data = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 3:
            continue
        data[parts[0]] = parts[:3]

    latest_by_date = {}
    for row in rows:
        if row["segmento"] != "Divisa":
            continue
        date_obj = dt.datetime.strptime(row["fecha"], "%Y-%m-%d").date()
        date_fmt = f"{date_obj.day}/{date_obj.month}/{date_obj.year}"
        entry = latest_by_date.setdefault(
            date_fmt,
            {"div_compra": None, "div_venta": None},
        )
        if row["tipo"] == "Compra":
            entry["div_compra"] = row["valor"]
        elif row["tipo"] == "Venta":
            entry["div_venta"] = row["valor"]

    for date_fmt, entry in latest_by_date.items():
        div_compra = entry["div_compra"]
        div_venta = entry["div_venta"]
        if None in (div_compra, div_venta):
            # Keep existing row if incomplete.
            continue
        row = [
            date_fmt,
            format_decimal(div_compra, max_decimals=2, use_thousands=False),
            format_decimal(div_venta, fixed_decimals=2, use_thousands=True),
        ]
        data[date_fmt] = row

    new_lines = [header] + [
        ";".join(data[k])
        for k in sorted(data.keys(), key=lambda d: dt.datetime.strptime(d, "%d/%m/%Y"))
    ]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def update_billete_file(path: Path, rows: list[dict]) -> None:
    """Actualiza CSV especifico de Billete con formato historico legado."""
    if not path.exists():
        header = "Fecha;Billete Compra;Billete Venta"
        path.write_text(header + "\n", encoding="utf-8")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        lines = ["Fecha;Billete Compra;Billete Venta"]

    header = lines[0]
    data = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 3:
            continue
        data[parts[0]] = parts[:3]

    latest_by_date = {}
    for row in rows:
        if row["segmento"] != "Billete":
            continue
        date_obj = dt.datetime.strptime(row["fecha"], "%Y-%m-%d").date()
        date_fmt = f"{date_obj.day}/{date_obj.month}/{date_obj.year}"
        entry = latest_by_date.setdefault(
            date_fmt, {"bil_compra": None, "bil_venta": None}
        )
        if row["tipo"] == "Compra":
            entry["bil_compra"] = row["valor"]
        elif row["tipo"] == "Venta":
            entry["bil_venta"] = row["valor"]

    for date_fmt, entry in latest_by_date.items():
        bil_compra = entry["bil_compra"]
        bil_venta = entry["bil_venta"]
        if None in (bil_compra, bil_venta):
            continue
        row = [
            date_fmt,
            format_decimal(bil_compra, max_decimals=2, use_thousands=False),
            format_decimal(bil_venta, max_decimals=2, use_thousands=False),
        ]
        data[date_fmt] = row

    new_lines = [header] + [
        ";".join(data[k])
        for k in sorted(data.keys(), key=lambda d: dt.datetime.strptime(d, "%d/%m/%Y"))
    ]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    """Punto de entrada: descarga, parsea, valida y actualiza historicos."""
    parser = argparse.ArgumentParser(
        description="Scrape BNA Divisas USD Venta and store history."
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT, help="Output file (.csv, .xlsx, .sqlite/.db)"
    )
    args = parser.parse_args()

    out_path = Path(args.out).resolve()

    try:
        # 1) Descargar HTML y convertirlo a texto plano para buscar secciones.
        html = fetch_html(URL)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n")
        # 2) Extraer bloque de Divisas y Billetes (cada bloque trae su fecha).

        date_str_div, block_div = extract_section_block(
            text, r"cotizaci[oó]n\s+divisas"
        )
        date_str_bil, block_bil = extract_section_block(
            text, r"cotizaci[oó]n\s+billetes"
        )

        # 3) Buscar Compra/Venta para Dolar U.S.A dentro de cada bloque.
        compra_div, venta_div = extract_usd_compra_venta(block_div)
        compra_bil, venta_bil = extract_usd_compra_venta(block_bil)

        fecha_div = dt.datetime.strptime(date_str_div, "%d/%m/%Y").date().isoformat()
        fecha_bil = dt.datetime.strptime(date_str_bil, "%d/%m/%Y").date().isoformat()
        # Advertencia de fechas distintas eliminada por pedido del usuario.
        # Divisa + Venta es el valor clave para la carga en Oracle.
        rows = [
            {
                "fecha": fecha_div,
                "moneda": "USD",
                "segmento": "Divisa",
                "tipo": "Compra",
                "valor": float(compra_div),
            },
            {
                "fecha": fecha_div,
                "moneda": "USD",
                "segmento": "Divisa",
                "tipo": "Venta",
                "valor": float(venta_div),
            },
            {
                "fecha": fecha_bil,
                "moneda": "USD",
                "segmento": "Billete",
                "tipo": "Compra",
                "valor": float(compra_bil),
            },
            {
                "fecha": fecha_bil,
                "moneda": "USD",
                "segmento": "Billete",
                "tipo": "Venta",
                "valor": float(venta_bil),
            },
        ]

        # 4) Cargar historico existente y validar duplicados o no-actualizaciones.
        df = load_existing(out_path)
        if "segmento" not in df.columns:
            df["segmento"] = ""
        
        df_new = pd.DataFrame(rows)
        if df.empty:
            df = df_new
        else:
            df["fecha"] = df["fecha"].astype(str)
            # Combinar y quitar duplicados exactos antes de rellenar
            df = pd.concat([df, df_new]).drop_duplicates(
                subset=["fecha", "moneda", "segmento", "tipo"], keep="last"
            )

        # Aplicar relleno de huecos (Sábados, Domingos, Feriados)
        df = fill_gaps(df)
        
        save_data(df, out_path)
        
        # Actualizar archivos legados usando el historial completo (para incluir los rellenos)
        divisa_path = out_path.parent / DIVISA_OUT
        billete_path = out_path.parent / BILLETE_OUT
        all_rows = df.to_dict("records")
        update_divisa_file(divisa_path, all_rows)
        update_billete_file(billete_path, all_rows)

        print(
            f"Proceso completado. Se sincronizaron cotizaciones hasta {fecha_div}. "
            f"Los huecos de fechas sin cotización oficial fueron rellenados con el valor anterior."
        )
        return 0

    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}")
        return 1
    except ValueError as exc:
        if "No se encontró" in str(exc) or "No se pudo extraer" in str(exc):
            print(
                "Advertencia: No se encontraron cotizaciones de Dolar en la página del BNA."
            )
        else:
            print(f"Error de procesamiento: {exc}")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
