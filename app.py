"""
Sistema de Reducción de Quinielas (Progol / Revancha)
------------------------------------------------------
App de Streamlit para armar un sistema de reducción de quinielas:
  1. Carga automática de la cartelera (equipos) de Progol y Revancha
     desde quinielaposible.com, o carga manual.
  2. Captura de cuotas de casino (manual o por archivo CSV/Excel).
  3. Por cada partido, tú eliges: un resultado fijo (L/E/V) o "DOBLE"
     (dos resultados posibles).
  4. Genera todas las combinaciones (2^numero_de_dobles quinielas).
  5. Filtros para descartar quinielas por número de empates, locales,
     visitantes o favoritos/no favoritos.
"""

import streamlit as st

from engine import (
    auto_marcar_dobles,
    blank_games_df,
    fetch_cartelera,
    fetch_media_semana,
    generar_quinielas,
    validar_dobles,
)

st.set_page_config(page_title="Sistema de Reducción de Quinielas", layout="wide")

st.title("🎯 Sistema de Reducción de Quinielas")
st.caption("Progol, Revancha y Media Semana — carga la cartelera, mete tus cuotas, marca dobles y filtra.")


@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch_cartelera():
    return fetch_cartelera()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch_media_semana():
    return fetch_media_semana()


def render_pool(tab_key, default_n, pool_label):
    st.subheader(pool_label)

    df_key = f"df_{tab_key}"
    ver_key = f"editor_ver_{tab_key}"
    if df_key not in st.session_state:
        st.session_state[df_key] = blank_games_df(default_n)
    if ver_key not in st.session_state:
        st.session_state[ver_key] = 0

    def _bump_editor():
        # Fuerza que el data_editor se reconstruya desde cero la próxima vez
        # (si no, mezcla su estado interno viejo con los datos nuevos y
        # las primeras celdas que edites a mano necesitan doble entrada).
        st.session_state[ver_key] += 1

    if st.button("🔄 Cargar cartelera automática", key=f"btn_cartelera_{tab_key}"):
        try:
            if tab_key == "media_semana":
                games, fuente = cached_fetch_media_semana()
            else:
                progol_games, revancha_games, fuente = cached_fetch_cartelera()
                games = progol_games if tab_key == "progol" else revancha_games
            if not games:
                st.error(f"No encontré partidos de '{pool_label}' en la fuente "
                          "(puede que este concurso no tenga esta modalidad).")
            else:
                df = st.session_state[df_key].copy()
                n = min(len(games), len(df))
                for i in range(n):
                    df.loc[i, "Local"] = games[i][0]
                    df.loc[i, "Visitante"] = games[i][1]
                st.session_state[df_key] = df
                _bump_editor()
                st.success(f"Cartelera cargada desde {fuente}")
        except RuntimeError as e:
            st.error(f"No se pudo cargar la cartelera automáticamente: {e}\n\n"
                     f"Puedes escribir los equipos a mano en la tabla de abajo.")

    st.caption("Captura las cuotas de casino directamente en la tabla de abajo (columnas Cuota_L / Cuota_E / Cuota_V).")

    col_c, col_d = st.columns([1, 2])
    with col_c:
        n_deseado = st.number_input(
            "¿Cuántos dobles quieres?", min_value=0, max_value=default_n, value=min(7, default_n),
            step=1, key=f"n_dobles_input_{tab_key}",
        )
    with col_d:
        st.write("")  # alinear verticalmente con el number_input
        if st.button(f"🎯 Marcar {n_deseado} dobles automáticamente", key=f"automark_{tab_key}"):
            try:
                nuevo_df = auto_marcar_dobles(st.session_state[df_key], n_deseado)
                st.session_state[df_key] = nuevo_df
                _bump_editor()
                st.success(f"Se marcaron los {n_deseado} partidos con cuotas más parejas como DOBLE "
                           f"(el resto quedó fijo con su favorito).")
            except ValueError as e:
                st.error(f"No se pudo marcar automáticamente: {e}\n\nLlena todas las cuotas primero.")

    edited = st.data_editor(
        st.session_state[df_key],
        key=f"editor_{tab_key}_{st.session_state[ver_key]}",
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "No": st.column_config.NumberColumn(disabled=True, width="small"),
            "Local": st.column_config.TextColumn(width="medium"),
            "Visitante": st.column_config.TextColumn(width="medium"),
            "Cuota_L": st.column_config.NumberColumn(format="%.2f", step=0.01),
            "Cuota_E": st.column_config.NumberColumn(format="%.2f", step=0.01),
            "Cuota_V": st.column_config.NumberColumn(format="%.2f", step=0.01),
            "Selección": st.column_config.SelectboxColumn(options=["L", "E", "V", "DOBLE"]),
            "Doble_Op1": st.column_config.SelectboxColumn(options=["", "L", "E", "V"]),
            "Doble_Op2": st.column_config.SelectboxColumn(options=["", "L", "E", "V"]),
        },
    )
    st.session_state[df_key] = edited

    n_dobles = int((edited["Selección"] == "DOBLE").sum())
    n_quinielas_previstas = 2 ** n_dobles
    c1, c2 = st.columns(2)
    c1.metric("Partidos marcados DOBLE", n_dobles)
    c2.metric("Quinielas que se generarán", f"{n_quinielas_previstas:,}")
    if n_dobles > 12:
        st.warning("Con más de 12 dobles el sistema puede volverse muy grande (miles de quinielas) y lento de filtrar.")

    if st.button("🎲 Generar sistema de reducción", key=f"gen_{tab_key}", type="primary"):
        ok, errores = validar_dobles(edited)
        if not ok:
            for e in errores:
                st.error(e)
        else:
            resultado, n = generar_quinielas(edited)
            st.session_state[f"result_{tab_key}"] = resultado
            st.success(f"Se generaron {n} quinielas.")

    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        st.markdown("### Quinielas generadas y filtros")
        res = st.session_state[result_key]
        max_n = len(edited)
        st.caption("Elige los valores que quieres **ELIMINAR** en cada columna (las quinielas con ese número desaparecen de la lista).")

        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        emp_excl = fc1.multiselect("Eliminar Empates =", list(range(0, max_n + 1)), key=f"emp_{tab_key}")
        loc_excl = fc2.multiselect("Eliminar Locales =", list(range(0, max_n + 1)), key=f"loc_{tab_key}")
        vis_excl = fc3.multiselect("Eliminar Visitantes =", list(range(0, max_n + 1)), key=f"vis_{tab_key}")
        if res["Favoritos"].notna().all():
            fav_excl = fc4.multiselect("Eliminar Favoritos =", list(range(0, max_n + 1)), key=f"fav_{tab_key}")
            nofav_excl = fc5.multiselect("Eliminar No_Favoritos =", list(range(0, max_n + 1)), key=f"nofav_{tab_key}")
        else:
            fav_excl, nofav_excl = [], []
            fc4.info("Faltan cuotas para filtrar por favoritos.")

        filtrado = res[
            ~res["Empates"].isin(emp_excl)
            & ~res["Locales"].isin(loc_excl)
            & ~res["Visitantes"].isin(vis_excl)
        ]
        if res["Favoritos"].notna().all():
            filtrado = filtrado[~filtrado["Favoritos"].isin(fav_excl) & ~filtrado["No_Favoritos"].isin(nofav_excl)]

        st.write(f"**Quinielas que sobreviven después de eliminar: {len(filtrado)} / {len(res)}**")
        st.dataframe(filtrado, use_container_width=True, height=400)

        csv = filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar quinielas filtradas (CSV)", csv,
                            file_name=f"quinielas_{tab_key}.csv", mime="text/csv",
                            key=f"dl_{tab_key}")


tab_progol, tab_revancha, tab_media_semana = st.tabs(
    ["Progol (14 partidos)", "Revancha (7 partidos)", "Media Semana (9 partidos)"]
)
with tab_progol:
    render_pool("progol", 14, "Progol — 14 partidos")
with tab_revancha:
    render_pool("revancha", 7, "Revancha — 7 partidos")
with tab_media_semana:
    render_pool("media_semana", 9, "Progol Media Semana — 9 partidos")

st.divider()
st.caption(
    "⚠️ El botón de cartelera automática trae los NOMBRES de los equipos desde quinielaposible.com "
    "(puede fallar si esa página cambia de formato). Las CUOTAS de casino no se cargan solas — "
    "no hay una fuente única y estable para momios en vivo — captúralas a mano o súbelas por CSV/Excel."
)
