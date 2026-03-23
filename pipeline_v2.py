"""
Termómetro del Barrio — Pipeline de datos SUACI
================================================
Descarga los CSV del SUACI desde BA Data, los procesa
y genera data.js para que index.html lo lea directamente.

Uso local:
    pip install pandas requests duckdb tqdm
    python pipeline.py --export

En GitHub Actions esto corre automáticamente cada semana.
"""

import os
import json
import argparse
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── URLs de descarga directa desde BA Data (CKAN) ──────────────────────────
# Cada año tiene su resource ID en el portal de datos abiertos de CABA.
# Si algún año falla (el GCBA a veces cambia los IDs), el script lo saltea
# y usa los años que sí funcionan.

SUACI_URLS = {
    2024: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/suaci-2024/download",
    2023: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/31ac3f7b-d99e-4b2f-8322-e4fc7b9cde3b/download",
    2022: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/f74143a6-919b-4664-97b4-93580ae7a45e/download",
    2021: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/3eb57505-84d5-4eff-810d-8f59fdc3aa20/download",
    2020: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/suaci-2020/download",
    2019: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/suaci-2019/download",
    2018: "https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana/resource/suaci-2018/download",
}

# ── Mapeo de rubros a categorías legibles ──────────────────────────────────
CATEGORIAS = {
    "LIMPIEZA URBANA":        "Limpieza",
    "ARBOLADO URBANO":        "Espacios verdes",
    "ARBOLADO":               "Espacios verdes",
    "ESPACIOS VERDES":        "Espacios verdes",
    "ALUMBRADO":              "Iluminación",
    "PAVIMENTO":              "Infraestructura vial",
    "SEÑALAMIENTO VIAL":      "Tránsito y seguridad vial",
    "TRANSITO":               "Tránsito y seguridad vial",
    "HIGIENE":                "Higiene y salud pública",
    "CONTROL DE PLAGAS":      "Higiene y salud pública",
    "AGUAS PLUVIALES":        "Inundaciones y desagüe",
    "INSTALACIONES":          "Infraestructura",
    "OBRAS PARTICULARES":     "Obras y construcción",
    "ESPACIO PUBLICO":        "Espacio público",
}

CATEGORIAS_CRITICAS = {
    "Infraestructura vial",
    "Inundaciones y desagüe",
    "Higiene y salud pública",
}

DATA_DIR = Path("./data_cache")  # carpeta temporal, no va al repo


# ── 1. DESCARGA ────────────────────────────────────────────────────────────

def descargar(año):
    """Descarga el CSV de un año. Devuelve el contenido como bytes o None."""
    DATA_DIR.mkdir(exist_ok=True)
    cache = DATA_DIR / f"suaci_{año}.csv"

    if cache.exists():
        print(f"  {año} → desde caché local")
        return cache.read_bytes()

    url = SUACI_URLS.get(año)
    if not url:
        return None

    try:
        r = requests.get(url, timeout=120, headers={"User-Agent": "termometro-barrio/1.0"})
        r.raise_for_status()
        cache.write_bytes(r.content)
        print(f"  {año} → descargado ({len(r.content)/1e6:.1f} MB)")
        return r.content
    except Exception as e:
        print(f"  {año} → error: {e}")
        return None


# ── 2. NORMALIZACIÓN ────────────────────────────────────────────────────────

COLUMNAS_POSIBLES = {
    "FECHA": "fecha", "fecha": "fecha",
    "RUBRO": "rubro", "rubro": "rubro",
    "CONCEPTO": "concepto", "concepto": "concepto",
    "BARRIO": "barrio", "barrio": "barrio",
    "COMUNA": "comuna", "comuna": "comuna",
}

def normalizar(contenido_bytes, año):
    """Lee bytes de CSV y devuelve DataFrame normalizado."""
    import io
    for enc in ["utf-8", "latin-1", "iso-8859-1"]:
        try:
            df = pd.read_csv(
                io.BytesIO(contenido_bytes),
                encoding=enc, sep=None, engine="python",
                low_memory=False, on_bad_lines="skip"
            )
            break
        except Exception:
            continue
    else:
        return None

    df.columns = [COLUMNAS_POSIBLES.get(c.strip(), c.strip().lower()) for c in df.columns]
    cols = [c for c in ["fecha", "rubro", "concepto", "barrio", "comuna"] if c in df.columns]
    df = df[cols].copy()

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
    df["año"]   = año  # usamos el año del archivo, más confiable que parsear fecha

    for col in ["rubro", "concepto", "barrio"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.upper().fillna("SIN DATO")

    df["categoria"] = df["rubro"].map(CATEGORIAS).fillna("Otros") if "rubro" in df.columns else "Otros"

    if "comuna" in df.columns:
        df["comuna"] = pd.to_numeric(df["comuna"], errors="coerce").fillna(0).astype(int)

    return df.dropna(subset=["barrio"])


# ── 3. CÁLCULO DE MÉTRICAS ─────────────────────────────────────────────────

def calcular_temperatura(total_reciente, total_anterior, reclamos_criticos, max_total):
    """
    Score 0–100 compuesto:
      - Volumen normalizado:   0–50 pts
      - Peso de categorías críticas: 0–30 pts
      - Tendencia interanual:  0–20 pts
    """
    vol   = (total_reciente / max_total) * 50 if max_total > 0 else 0
    crit  = (reclamos_criticos / total_reciente) * 30 if total_reciente > 0 else 0
    if total_anterior and total_anterior > 0:
        ratio = total_reciente / total_anterior
        tend  = 20 if ratio > 1.1 else (0 if ratio < 0.9 else 10)
    else:
        tend = 10
    return round(min(100, vol + crit + tend), 1)


def construir_metricas(df):
    """
    A partir del DataFrame consolidado, calcula todos los indicadores
    necesarios por barrio y devuelve un dict listo para data.js.
    """
    año_max   = df["año"].max()
    año_ant   = año_max - 1

    recientes  = df[df["año"] == año_max]
    anteriores = df[df["año"] == año_ant]

    # Total por barrio para normalizar temperatura
    totales_recientes = recientes.groupby("barrio").size()
    max_total = totales_recientes.max()

    resultado = {}

    for barrio, grupo in recientes.groupby("barrio"):
        if len(barrio) < 3:
            continue

        total_rec  = len(grupo)
        total_ant  = len(anteriores[anteriores["barrio"] == barrio])
        criticos   = len(grupo[grupo["categoria"].isin(CATEGORIAS_CRITICAS)])

        # Tendencia porcentual
        tend_pct = round((total_rec - total_ant) / total_ant * 100) if total_ant > 0 else 0

        temperatura = calcular_temperatura(total_rec, total_ant, criticos, max_total)

        # Top 5 conceptos
        top = (
            grupo.groupby(["concepto", "categoria"])
            .size()
            .reset_index(name="total")
            .sort_values("total", ascending=False)
            .head(5)
        )
        max_top = top["total"].iloc[0] if len(top) > 0 else 1

        # Tendencia por concepto vs año anterior
        concs_ant = anteriores[anteriores["barrio"] == barrio].groupby("concepto").size()

        problemas = []
        for _, row in top.iterrows():
            ant = concs_ant.get(row["concepto"], 0)
            rec = row["total"]
            if   rec > ant * 1.08: tend = "▲"
            elif rec < ant * 0.92: tend = "▼"
            else:                  tend = "→"
            problemas.append({
                "nombre":    row["concepto"].title(),
                "categoria": row["categoria"],
                "total":     int(rec),
                "pct":       round(rec / max_top * 100),
                "tendencia": tend,
            })

        # Histórico anual (hasta 7 años)
        historico = []
        for y in range(año_max - 6, año_max + 1):
            n = len(df[(df["año"] == y) & (df["barrio"] == barrio)])
            historico.append(int(n))

        # Comuna más frecuente en los datos del barrio
        if "comuna" in grupo.columns:
            comuna = int(grupo["comuna"].mode().iloc[0]) if len(grupo) > 0 else 0
        else:
            comuna = 0

        slug = (
            barrio.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("á","a").replace("é","e").replace("í","i")
            .replace("ó","o").replace("ú","u").replace("ü","u")
            .replace("ñ","n")
        )

        resultado[slug] = {
            "nombre":        barrio.title(),
            "comuna":        comuna,
            "temperatura":   temperatura,
            "totalReclamos": int(total_rec),
            "tendenciaPct":  int(tend_pct),
            "problemas":     problemas,
            "historico":     historico,
        }

    return resultado, int(año_max)


# ── 4. GENERAR data.js ─────────────────────────────────────────────────────

def generar_data_js(metricas, año_max):
    """Escribe data.js listo para ser leído por index.html."""
    promedio = round(
        sum(b["temperatura"] for b in metricas.values()) / len(metricas), 1
    ) if metricas else 55.0

    ahora = datetime.now().strftime("%Y-%m-%d")

    js = f"""/*
  data.js — Termómetro del Barrio · CABA
  Generado automáticamente por pipeline.py el {ahora}
  Fuente: SUACI / BA Data · data.buenosaires.gob.ar
  Datos reales — mock: false
*/

const DATOS_MOCK = false;
const AÑO_DATOS = {año_max};
const FECHA_ACTUALIZACION = "{ahora}";

const BARRIOS_DATA = {json.dumps(metricas, ensure_ascii=False, indent=2)};

const TEMP_PROMEDIO_CABA = {promedio};
"""
    Path("data.js").write_text(js, encoding="utf-8")
    print(f"\n✅ data.js generado — {len(metricas)} barrios · promedio CABA: {promedio}°")


# ── MAIN ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true",
                        help="Generar data.js al final (requerido para actualizar la web)")
    parser.add_argument("--full", action="store_true",
                        help="Descargar historial completo 2018-2024 (por defecto: 2022-2024)")
    args = parser.parse_args()

    años = list(SUACI_URLS.keys()) if args.full else [2024, 2023, 2022]

    print(f"🌡  Termómetro del Barrio — Pipeline")
    print(f"   Años a procesar: {años}\n")

    # 1. Descargar y normalizar
    frames = []
    for año in sorted(años):
        contenido = descargar(año)
        if contenido:
            df_año = normalizar(contenido, año)
            if df_año is not None and len(df_año) > 0:
                frames.append(df_año)
                print(f"  {año} → {len(df_año):,} reclamos normalizados")

    if not frames:
        print("❌ No se pudo procesar ningún año. Revisá las URLs en SUACI_URLS.")
        exit(1)

    df_total = pd.concat(frames, ignore_index=True)
    print(f"\n  Total: {len(df_total):,} reclamos en {df_total['año'].nunique()} años")
    print(f"  Barrios únicos: {df_total['barrio'].nunique()}")

    # 2. Calcular métricas
    print("\nCalculando métricas por barrio...")
    metricas, año_max = construir_metricas(df_total)
    print(f"  {len(metricas)} barrios procesados")

    # 3. Generar data.js
    if args.export:
        generar_data_js(metricas, año_max)
    else:
        print("\n(Usá --export para generar data.js)")
