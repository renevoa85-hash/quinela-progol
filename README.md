# Sistema de Reducción de Quinielas

App de Streamlit para armar sistemas de reducción de quinielas (Progol, Revancha
y Progol Media Semana):

- Carga automática de la cartelera (equipos) de cada concurso vigente desde
  quinielaposible.com.
- Captura manual de cuotas de casino (Cuota_L / Cuota_E / Cuota_V).
- Marca automáticamente los N partidos más parejos como "DOBLE" (o los marcas
  tú a mano), y el resto queda "FIJO" con su favorito.
- Genera todas las combinaciones (2^dobles quinielas).
- Filtros para eliminar quinielas por número de empates, locales, visitantes,
  favoritos o no favoritos.

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

En Windows también puedes usar `Iniciar_Quiniela.bat` (doble clic).

## Estructura

- `app.py` — interfaz (Streamlit).
- `engine.py` — lógica pura (sin dependencias de Streamlit), incluye el
  scraper de cartelera y el generador de combinaciones. Se puede probar
  directo con `python -c "import engine; ..."`.

## Notas

- El botón de cartelera automática depende de la estructura HTML de
  quinielaposible.com — si esa página cambia de formato, puede dejar de
  funcionar (mostrará un mensaje de error claro, no falla en silencio).
- Las cuotas de casino se capturan a mano — no hay una fuente automática
  confiable y gratuita para momios en vivo de todas las ligas que cubre
  Progol.
- La app no persiste datos entre sesiones: si recargas la página, se pierde
  lo capturado.
