import streamlit as st
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import random
import math
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Patrones Sociales 2", layout="centered")

st.markdown("""
<style>
.agente-box { padding: 12px; border-radius: 10px; margin-bottom: 10px; }
.a { background-color: rgba(0,0,255,0.05); border-left: 5px solid blue; }
.b { background-color: rgba(0,255,0,0.05); border-left: 5px solid green; }
</style>
""", unsafe_allow_html=True)

st.title("📍 Patrones Sociales – Simulación de Encuentros")
st.caption("Modelo experimental de recorridos urbanos y coincidencias espacio-temporales")

# ---------------- ESTADO ----------------
if "resultado" not in st.session_state:
    st.session_state.resultado = None
if "figura" not in st.session_state:
    st.session_state.figura = None

# ---------------- PARAMETROS ----------------
MODALIDADES = {
    "Paseo": 1.0 / 3.6,
    "Normal": 2.5 / 3.6,
    "Rápido": 3.3 / 3.6
}

st.subheader("Configuración")

# -------- BARRIO --------
place = st.text_input("Zona / Barrio", "Recoleta, Buenos Aires, Argentina")

# ---------------- FUNCIONES ----------------
@st.cache_data
def cargar_grafo(lugar):
    G = ox.graph_from_place(lugar, network_type="walk")
    Gp = ox.project_graph(G)
    nodes = ox.graph_to_gdfs(G, edges=False)
    centro = [nodes.geometry.y.mean(), nodes.geometry.x.mean()]
    return G, Gp, nodes, centro

def simular(G, path, t0, vel):
    t = t0
    salida = []
    for u, v in zip(path[:-1], path[1:]):
        d = list(G.get_edge_data(u, v).values())[0]["length"]
        salida.append((u, t))
        t += timedelta(seconds=d / vel)
    salida.append((path[-1], t))
    return salida

# ---------------- MAPA ----------------
G, Gp, nodes_gdf, centro = cargar_grafo(place)

st.subheader("Área de posible encuentro (rectángulo)")

m = folium.Map(location=centro, zoom_start=15)

Draw(
    draw_options={
        "rectangle": True,
        "polygon": False,
        "polyline": False,
        "circle": False,
        "marker": False,
        "circlemarker": False
    },
    edit_options={"edit": False}
).add_to(m)

mapa = st_folium(m, height=360, use_container_width=True)

# ---------------- SLIDERS ----------------
st.subheader("Parámetros de los agentes")

col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="agente-box a"><b>Agente A</b>', unsafe_allow_html=True)
    ha = st.slider("Hora salida A", 0, 23, 9)
    ma = st.slider("Minuto salida A", 0, 59, 0)
    va = st.selectbox("Velocidad A", MODALIDADES.keys())
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="agente-box b"><b>Agente B</b>', unsafe_allow_html=True)
    hb = st.slider("Hora salida B", 0, 23, 9)
    mb = st.slider("Minuto salida B", 0, 59, 5)
    vb = st.selectbox("Velocidad B", MODALIDADES.keys())
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- EJECUCION ----------------
if st.button("▶ Ejecutar simulación", use_container_width=True):

    st.session_state.resultado = None
    st.session_state.figura = None

    if not mapa or not mapa.get("all_drawings"):
        st.session_state.resultado = ("error", "No se definió un rectángulo.")
    else:
        rect = mapa["all_drawings"][-1]["geometry"]["coordinates"][0]
        lons, lats = zip(*rect)
        bbox = [min(lats), max(lats), min(lons), max(lons)]

        nodos_area = nodes_gdf.cx[bbox[2]:bbox[3], bbox[0]:bbox[1]].index.tolist()
        nodos_fuera = nodes_gdf.index.difference(nodos_area).tolist()

        if len(nodos_area) < 1 or len(nodos_fuera) < 2:
            st.session_state.resultado = ("error", "Área sin calles válidas.")
        else:
            cp = random.choice(nodos_area)
            oa, da = random.sample(nodos_fuera, 2)
            ob, db = random.sample(nodos_fuera, 2)

            pa = nx.shortest_path(Gp, oa, cp, weight="length")[:-1] + nx.shortest_path(Gp, cp, da, weight="length")
            pb = nx.shortest_path(Gp, ob, cp, weight="length")[:-1] + nx.shortest_path(Gp, cp, db, weight="length")

            now = datetime.now().replace(second=0, microsecond=0)
            ra = simular(Gp, pa, now.replace(hour=ha, minute=ma), MODALIDADES[va])
            rb = simular(Gp, pb, now.replace(hour=hb, minute=mb), MODALIDADES[vb])

            encontro = None
            for na, ta in ra:
                for nb, tb in rb:
                    dist = math.hypot(Gp.nodes[na]["x"] - Gp.nodes[nb]["x"],
                                      Gp.nodes[na]["y"] - Gp.nodes[nb]["y"])
                    if abs((ta - tb).total_seconds()) <= 60 and dist <= 20:
                        encontro = (na, ta)
                        break
                if encontro:
                    break

            fig, ax = plt.subplots(figsize=(8, 8))
            ox.plot_graph(Gp, ax=ax, show=False, close=False,
                          node_size=0, edge_color="#ddd", edge_linewidth=0.6)

            ox.plot_graph_route(Gp, pa, ax=ax, route_color="blue", route_alpha=0.4, show=False)
            ox.plot_graph_route(Gp, pb, ax=ax, route_color="green", route_alpha=0.4, show=False)

            for n, txt, col in [(oa, "INICIO A", "blue"), (da, "FIN A", "blue"),
                                (ob, "INICIO B", "green"), (db, "FIN B", "green")]:
                ax.scatter(Gp.nodes[n]["x"], Gp.nodes[n]["y"], c=col, s=70, zorder=5)
                ax.annotate(txt, (Gp.nodes[n]["x"], Gp.nodes[n]["y"]),
                            xytext=(10, 10), textcoords="offset points",
                            fontsize=8, fontweight="bold",
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col))

            if encontro:
                n, t = encontro
                ax.scatter(Gp.nodes[n]["x"], Gp.nodes[n]["y"], c="red", s=140, zorder=6)
                ax.annotate(f"ENCUENTRO\n{t.strftime('%H:%M')}",
                            (Gp.nodes[n]["x"], Gp.nodes[n]["y"]),
                            xytext=(0, 25), textcoords="offset points",
                            ha="center", fontsize=9, fontweight="bold",
                            bbox=dict(boxstyle="round", fc="red", ec="white"),
                            color="white")
                st.session_state.resultado = ("ok", f"Encuentro detectado a las {t.strftime('%H:%M')}")
            else:
                st.session_state.resultado = ("info", "No se produjo encuentro (tiempo o espacio).")

            st.session_state.figura = fig

# ---------------- RESULTADO ----------------
if st.session_state.resultado:
    tipo, texto = st.session_state.resultado
    if tipo == "ok":
        st.success(texto)
    elif tipo == "info":
        st.info(texto)
    else:
        st.error(texto)

if st.session_state.figura:
    st.pyplot(st.session_state.figura)
