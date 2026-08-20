"""Lógica pura del sistema de reducción de quinielas (sin dependencias de
Streamlit) — separada para poder probarla directamente."""

import itertools

import pandas as pd
import requests
from bs4 import BeautifulSoup

LETTERS = ["L", "E", "V"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CATEGORY_PROGOL = "https://quinielaposible.com/category/progol/"
CATEGORY_MEDIA_SEMANA = "https://quinielaposible.com/category/progol-media-semana/"


def _latest_article_link(category_url, href_hint):
    try:
        r = requests.get(category_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"No se pudo contactar quinielaposible.com ({e})")

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select("h2.entry-title a, h3.entry-title a"):
        href = a.get("href", "")
        if href_hint in href:
            return href
    for a in soup.find_all("a", href=True):
        if href_hint in a["href"]:
            return a["href"]
    raise RuntimeError("No encontré el enlace del concurso más reciente en la página índice.")


def _parse_team_table(article_url, split_on_marker=None):
    """Descarga article_url y extrae filas de equipos de la primera tabla.
    Si split_on_marker se da (texto en minúsculas, ej. 'revancha'), separa
    los partidos en (antes, después) de la fila marcador; si no, regresa
    (todos, [])."""
    try:
        r = requests.get(article_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir la página del concurso ({e})")

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("La página del concurso no tiene la tabla de partidos esperada.")

    rows = tables[0].find_all("tr")
    antes, despues = [], []
    after_marker = False
    for row in rows:
        cells = row.find_all("td")
        classes_flat = " ".join(" ".join(c.get("class", [])) for c in cells)
        if split_on_marker and len(cells) == 1 and split_on_marker in cells[0].get_text(strip=True).lower():
            after_marker = True
            continue
        if len(cells) == 5 and "qp-pred-team" in classes_flat:
            local = cells[1].get_text(strip=True)
            visit = cells[3].get_text(strip=True)
            (despues if after_marker else antes).append((local, visit))

    return antes, despues


def fetch_cartelera():
    """Descarga la cartelera vigente de Progol (14) y Revancha (7) desde
    quinielaposible.com. Devuelve (progol_games, revancha_games, fuente_url)
    donde cada *_games es una lista de tuplas (local, visitante).
    Lanza RuntimeError con un mensaje claro si algo falla."""
    latest = _latest_article_link(CATEGORY_PROGOL, "quiniela-pronostico-y-fijos")
    progol_games, revancha_games = _parse_team_table(latest, split_on_marker="revancha")
    if len(progol_games) < 7:
        raise RuntimeError("No logré extraer suficientes partidos de la tabla (formato de la página cambió).")
    return progol_games, revancha_games, latest


def fetch_media_semana():
    """Descarga la cartelera vigente de Progol Media Semana (9 partidos)
    desde quinielaposible.com. Devuelve (games, fuente_url)."""
    latest = _latest_article_link(CATEGORY_MEDIA_SEMANA, "progol-media-semana")
    games, _ = _parse_team_table(latest, split_on_marker=None)
    if len(games) < 5:
        raise RuntimeError("No logré extraer suficientes partidos de la tabla (formato de la página cambió).")
    return games, latest


def blank_games_df(n):
    return pd.DataFrame({
        "No": list(range(1, n + 1)),
        "Local": [""] * n,
        "Visitante": [""] * n,
        "Cuota_L": [None] * n,
        "Cuota_E": [None] * n,
        "Cuota_V": [None] * n,
        "Selección": ["L"] * n,
        "Doble_Op1": [""] * n,
        "Doble_Op2": [""] * n,
    })


def favorito_de(row):
    """Favorito 'general' (para elegir el pick fijo de un partido): la
    letra con la cuota más baja entre L, E y V."""
    odds = {"L": row["Cuota_L"], "E": row["Cuota_E"], "V": row["Cuota_V"]}
    if any(pd.isna(v) or v in (None, "") for v in odds.values()):
        return None
    return min(odds, key=odds.get)


def favorito_no_favorito_de(row):
    """Favorito / No favorito para efectos de filtrado: se decide
    ÚNICAMENTE entre Local y Visitante, ignorando el Empate por completo
    (aunque el Empate tenga la misma cuota que uno de los dos, o incluso
    menor). Ej: León 2.8 / Empate 2.5 / Monterrey 1.5 -> favorito=Monterrey(V),
    no_favorito=León(L). Devuelve (favorito, no_favorito) como 'L'/'V', o
    (None, None) si faltan cuotas."""
    cl, cv = row["Cuota_L"], row["Cuota_V"]
    if pd.isna(cl) or cl in (None, "") or pd.isna(cv) or cv in (None, ""):
        return None, None
    if cl <= cv:
        return "L", "V"
    return "V", "L"


def auto_marcar_dobles(df, n_dobles):
    """Devuelve una copia de df con exactamente n_dobles partidos marcados
    como DOBLE — los de cuotas más parejas (menor diferencia entre las dos
    cuotas más bajas) — y el resto en FIJO con su favorito (cuota más baja).
    Requiere que TODAS las cuotas estén completas; si no, lanza ValueError
    señalando qué partido falta."""
    df = df.copy()
    n_games = len(df)
    n_dobles = max(0, min(int(n_dobles), n_games))

    gaps = []
    for i, row in df.iterrows():
        odds = {"L": row["Cuota_L"], "E": row["Cuota_E"], "V": row["Cuota_V"]}
        if any(pd.isna(v) or v in (None, "") for v in odds.values()):
            raise ValueError(
                f"Partido {row['No']} ({row['Local']} vs {row['Visitante']}) "
                f"no tiene las 3 cuotas completas."
            )
        vals = sorted(odds.values())
        gaps.append((vals[1] - vals[0], i))

    gaps.sort(key=lambda t: (t[0], t[1]))
    dobles_idx = {i for _, i in gaps[:n_dobles]}

    for i, row in df.iterrows():
        odds = {"L": row["Cuota_L"], "E": row["Cuota_E"], "V": row["Cuota_V"]}
        if i in dobles_idx:
            dos_mas_bajas = sorted(odds, key=odds.get)[:2]
            df.loc[i, "Selección"] = "DOBLE"
            df.loc[i, "Doble_Op1"] = dos_mas_bajas[0]
            df.loc[i, "Doble_Op2"] = dos_mas_bajas[1]
        else:
            df.loc[i, "Selección"] = min(odds, key=odds.get)
            df.loc[i, "Doble_Op1"] = ""
            df.loc[i, "Doble_Op2"] = ""

    return df


def validar_dobles(df):
    """Devuelve (ok, lista_de_errores) validando cada fila."""
    errores = []
    for _, row in df.iterrows():
        sel = row["Selección"]
        if sel == "DOBLE":
            ops = {row["Doble_Op1"], row["Doble_Op2"]}
            ops.discard("")
            if len(ops) != 2:
                errores.append(f"Partido {row['No']} ({row['Local']} vs {row['Visitante']}): "
                                f"elige exactamente 2 opciones distintas para el DOBLE.")
        elif sel not in LETTERS:
            errores.append(f"Partido {row['No']}: selección inválida.")
    return (len(errores) == 0), errores


def generar_quinielas(df):
    """df ya validado. Devuelve (DataFrame, n_combos)."""
    picks_por_partido = []
    for _, row in df.iterrows():
        if row["Selección"] == "DOBLE":
            picks_por_partido.append(sorted({row["Doble_Op1"], row["Doble_Op2"]}))
        else:
            picks_por_partido.append([row["Selección"]])

    n_combos = 1
    for p in picks_por_partido:
        n_combos *= len(p)

    combos = list(itertools.product(*picks_por_partido))
    n_games = len(df)
    col_names = [f"P{i+1}" for i in range(n_games)]
    data = {name: [c[i] for c in combos] for i, name in enumerate(col_names)}
    out = pd.DataFrame(data)
    out.insert(0, "Q#", range(1, len(out) + 1))

    out["Empates"] = (out[col_names] == "E").sum(axis=1)
    out["Locales"] = (out[col_names] == "L").sum(axis=1)
    out["Visitantes"] = (out[col_names] == "V").sum(axis=1)

    fav_nofav = [favorito_no_favorito_de(row) for _, row in df.iterrows()]
    if all(f is not None for f, _ in fav_nofav):
        fav_match, nofav_match = None, None
        for i, name in enumerate(col_names):
            fav_letra, nofav_letra = fav_nofav[i]
            mf = (out[name] == fav_letra).astype(int)
            mn = (out[name] == nofav_letra).astype(int)
            fav_match = mf if fav_match is None else fav_match + mf
            nofav_match = mn if nofav_match is None else nofav_match + mn
        out["Favoritos"] = fav_match
        out["No_Favoritos"] = nofav_match
    else:
        out["Favoritos"] = None
        out["No_Favoritos"] = None

    return out, n_combos
