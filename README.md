# Dolar BNA Divisa

Script en Python 3.x para obtener diariamente la cotización del **Dólar U.S.A** en **Divisas** y **Billetes** desde la web pública del Banco Nación Argentina (BNA) y mantener un histórico.

El valor clave para la carga en Oracle es:

- `segmento = "Divisa"` y `tipo = "Venta"`

## Objetivo

- Descargar la página de BNA Personas.
- Identificar las secciones de **Cotización Divisas** y **Cotización Billetes**.
- Extraer **Compra/Venta** de **Dólar U.S.A**.
- Actualizar un histórico idempotente.
- Asegurar la sincronización de archivos de legado para compatibilidad.

## Archivos de Salida

### 1) Histórico Maestro (`--out`)

Es el archivo principal de seguimiento del script (por defecto `bna_divisa_hist.csv`). Se usa para detectar si los datos del día ya fueron procesados.
Columnas: `fecha` (YYYY-MM-DD), `moneda`, `segmento`, `tipo`, `valor`.

### 2) Archivos de Legado (Secundarios)

Se actualizan automáticamente para mantener compatibilidad con sistemas externos:

- `bna_dolar_divisa_hist.csv`: Formato específico de Divisas con separador `;`.
- `bna_dolar_billete_hist.csv`: Formato específico de Billetes con separador `;`.

## Instalación

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

## Uso

```bash
python bna_divisa.py --out bna_divisa_hist.csv
```

## Mensajes de Salida

El script informa su estado de forma concisa:

- `ya existian valores para la fecha dd/mm/aaaa, Actualizado`: Los datos ya están en el maestro, pero se verificó/corrigió la integridad de los archivos de legado.
- `se agregaron USD aaaa-mm-dd: ...`: Se detectaron y guardaron nuevos registros.
- `Advertencia: No se encontraron cotizaciones...`: Problema al extraer datos de la web (cambio de HTML o caída del sitio).

## Automatización (Windows)

Se recomienda el uso de **Task Scheduler** (Programador de Tareas) para ejecutar el script diariamente por la tarde (ej. 16:00 hs), cuando el BNA ya suele haber actualizado los cierres.

## Soporte

Ante cambios estructurales en la web del BNA, contactar a soporte o revisar las funciones de extracción en `bna_divisa.py`.
