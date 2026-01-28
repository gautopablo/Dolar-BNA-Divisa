# Dolar BNA Divisa

Script en Python 3.x para obtener diariamente la cotizacion del **Dolar U.S.A** en **Divisas** y **Billetes** desde la web publica del Banco Nacion Argentina (BNA) y guardar un historico.

El valor clave para carga en Oracle es:
- `segmento = "Divisa"` y `tipo = "Venta"`

## Objetivo
- Descargar la pagina de BNA Personas.
- Identificar la seccion **Cotizacion Divisas** y **Cotizacion Billetes**.
- Extraer **Compra/Venta** de **Dolar U.S.A**.
- Actualizar un historico idempotente (sin duplicar fecha/moneda/segmento/tipo).
- Registrar cuando el valor no cambia respecto al ultimo registro.

## Requisitos
- Python 3.x
- Paquetes: `requests`, `beautifulsoup4`, `pandas`
- Fuente: https://www.bna.com.ar/Personas

## Instalacion
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso
```bash
python bna_divisa.py --out bna_divisa_hist.csv
```

El parametro `--out` puede ser:
- CSV: `bna_divisa_hist.csv` (default)
- Excel: `bna_divisa_hist.xlsx`
- SQLite: `bna_divisa_hist.sqlite` o `.db`

## Salidas
### 1) Historico principal
Archivo indicado por `--out`, con columnas:
- `fecha` (YYYY-MM-DD)
- `moneda` (USD)
- `segmento` (Divisa o Billete)
- `tipo` (Compra o Venta)
- `valor` (float)

**Valor a cargar en Oracle:**
- `segmento = "Divisa"` y `tipo = "Venta"`

### 2) CSVs secundarios (legado)
El script tambien actualiza:
- `bna_dolar_divisa_hist.csv`
- `bna_dolar_billete_hist.csv`

## Formato decimal y separadores
- En el historico principal (`--out`), `valor` es **float**.
- En los CSVs secundarios, se usa `;` como separador y `,` como decimal.

## Idempotencia
- Si ya existen los 4 registros (Divisa/Billete, Compra/Venta) para la fecha, no se duplican.

## Logs esperados
- Mensajes de no-actualizacion si el valor coincide con el ultimo registro.
- Advertencia si la fecha de Divisa y Billete no coincide.

## Automatizacion (Linux)
Ejemplo cron (17:00 GMT-3):
```bash
0 17 * * * /ruta/python /ruta/proyecto/bna_divisa.py --out /ruta/proyecto/bna_divisa_hist.csv >> /ruta/proyecto/bna_divisa.log 2>&1
```

## Automatizacion (Windows)
Usar Task Scheduler para ejecutar el mismo comando con Python.

## Nota sobre Oracle
La insercion en Oracle la realiza IT. Este script deja el valor identificado para su carga.

## Soporte
Ante cambios en el HTML de BNA, revisar las funciones:
- `extract_section_block`
- `extract_usd_compra_venta`
