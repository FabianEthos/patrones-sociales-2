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
st.set_page_config(layout="wide", page_title="Encuentro Urbano")

st.markdown("""
    <style>
    .agente-a-box { background-color: rgba(0, 0, 255, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid blue; }
    .agente-b-box { background-color: rgba(0, 255, 0, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid green; }
    </style>
    """, unsafe_allow_html=True)

st.title("📍 Simulación: Dinámica de Encuentro")
st.caption("Ajusta velocidades y tiempos para observar cómo varían los puntos de contacto.")

# ---------------- SIDEBAR: CONFIGURACIÓN ----------------
MODALIDADES = {
    'Paseo (1.0 km/h)': 1.0 / 3.6,   # Convertido a m/s
    'Normal (2.5 km/h)': 2.5 / 3.6,
    'Rápido (4.0 km/h)': 3.3 / 3.6
}

with st.sidebar:
    st.header("⚙️ Parámetros")
    place = st.text_input("Barrio / Zona", "Recoleta, Buenos Aires, Argentina")
    
    st.markdown("---")
    
    # AGENTE A
    st.markdown('<div class="agente-a-box"><b>🚶‍♂️ Agente A (Azul)</b>', unsafe_allow_html=True)
    h_a = st.slider("Hora de salida (A)", 0, 23, 9, key="ha")
    m_a = st.slider("Minuto de salida (A)", 0, 59, 0, key="ma")
    vel_a_key = st.selectbox("Ritmo de marcha (A)", list(MODALIDADES.keys()), index=1, key="va")
    st.markdown('</div><br>', unsafe_allow_html=True)
    
    # AGENTE B
    st.markdown('<div class="agente-b-box"><b>🚶‍♀️ Agente B (Verde)</b>', unsafe_allow_html=True)
    h_b = st.slider("Hora de salida (B)", 0, 23, 9, key="hb")
    m_b = st.slider("Minuto de salida (B)", 0, 59, 5, key="mb")
    vel_b_key = st.selectbox("Ritmo de marcha (B)", list(MODALIDADES.keys()), index=1, key="vb")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- FUNCIONES ----------------
@st.cache_data
def cargar_mapa(lugar):
    G = ox.graph_from_place(lugar, network_type="walk")
    G_proj = ox.project_graph(G)
    nodes_gdf = ox.graph_to_gdfs(G, edges=False)
    centro = [nodes_gdf.geometry.y.mean(), nodes_gdf.geometry.x.mean()]
    return G, G_proj, centro

def simular_recorrido(G, path, hora_inicio, velocidad_mps):
    tiempo = hora_inicio
    timeline = []
    for u, v in zip(path[:-1], path[1:]):
        data = G.get_edge_data(u, v)
        dist = data[0]['length'] if 0 in data else data['length']
        timeline.append((u, tiempo))
        # El tiempo de viaje depende ahora de la modalidad elegida
        tiempo += timedelta(seconds=dist / velocidad_mps)
    timeline.append((path[-1], tiempo))
    return timeline

# ---------------- FLUJO PRINCIPAL ----------------
try:
    G_geo, G_proj, centro = cargar_mapa(place)

    st.subheader("1. Definir área de interés intermedio")
    m = folium.Map(location=centro, zoom_start=15)
    Draw(draw_options={'polyline':False, 'circle':False, 'marker':False, 'polygon':False, 'circlemarker':False}).add_to(m)
    output = st_folium(m, width=1000, height=400, key="mapa_checkpoint")

    if output and output.get("all_drawings"):
        poly = output["all_drawings"][-1]["geometry"]["coordinates"][0]
        lons, lats = zip(*poly)
        bbox = [min(lats), max(lats), min(lons), max(lons)]
        
        if st.button("🔥 Ejecutar Simulación Temporal", use_container_width=True):
            nodes_gdf = ox.graph_to_gdfs(G_geo, edges=False)
            nodos_en_area = nodes_gdf.cx[bbox[2]:bbox[3], bbox[0]:bbox[1]].index.tolist()
            nodos_fuera = nodes_gdf.index.difference(nodos_en_area).tolist()

            if not nodos_en_area:
                st.error("El área no contiene nodos (calles). Dibújala sobre una manzana o calle.")
            else:
                # Lógica Checkpoint
                cp_a, cp_b = random.choice(nodos_en_area), random.choice(nodos_en_area)
                oa, da = random.sample(nodos_fuera, 2)
                ob, db = random.sample(nodos_fuera, 2)

                path_a = nx.shortest_path(G_proj, oa, cp_a, weight="length")[:-1] + nx.shortest_path(G_proj, cp_a, da, weight="length")
                path_b = nx.shortest_path(G_proj, ob, cp_b, weight="length")[:-1] + nx.shortest_path(G_proj, cp_b, db, weight="length")

                # Simulación con velocidades variables
                t_ref = datetime.now().replace(second=0, microsecond=0)
                rec_a = simular_recorrido(G_proj, path_a, t_ref.replace(hour=h_a, minute=m_a), MODALIDADES[vel_a_key])
                rec_b = simular_recorrido(G_proj, path_b, t_ref.replace(hour=h_b, minute=m_b), MODALIDADES[vel_b_key])

                # Detección de encuentro
                nodo_enc, hora_enc = None, None
                for na, ta in rec_a:
                    for nb, tb in rec_b:
                        d = math.sqrt((G_proj.nodes[na]['x']-G_proj.nodes[nb]['x'])**2 + (G_proj.nodes[na]['y']-G_proj.nodes[nb]['y'])**2)
                        # Margen de 1 minuto y 20 metros
                        if abs((ta - tb).total_seconds()) <= 60 and d <= 20:
                            nodo_enc, hora_enc = na, ta
                            break
                    if nodo_enc: break

                # --- PLOT ---
                fig, ax = plt.subplots(figsize=(10, 10))
                ox.plot_graph(G_proj, ax=ax, show=False, close=False, node_size=0, edge_color="#f0f0f0", edge_linewidth=0.6)
                ox.plot_graph_route(G_proj, path_a, ax=ax, route_color="blue", route_linewidth=2, route_alpha=0.3, show=False)
                ox.plot_graph_route(G_proj, path_b, ax=ax, route_color="green", route_linewidth=2, route_alpha=0.3, show=False)

                puntos_clave = [
                    (oa, f"INICIO A\n({vel_a_key})", "blue", (-50, 20)),
                    (da, "FIN A", "blue", (50, 20)),
                    (ob, f"INICIO B\n({vel_b_key})", "green", (-50, -20)),
                    (db, "FIN B", "green", (50, -20))
                ]

                for n, txt, color, offset in puntos_clave:
                    node = G_proj.nodes[n]
                    ax.scatter(node['x'], node['y'], c=color, s=60, zorder=5)
                    ax.annotate(f"{txt}\nID:{n}", (node['x'], node['y']), xytext=offset,
                                textcoords='offset points', fontsize=7, fontweight='bold',
                                arrowprops=dict(arrowstyle='->', color=color, alpha=0.5),
                                bbox=dict(boxstyle="round,pad=0.2", fc="w", ec=color, alpha=0.8))

                if nodo_enc:
                    node = G_proj.nodes[nodo_enc]
                    ax.scatter(node['x'], node['y'], c="red", s=150, zorder=6, edgecolor='white')
                    ax.annotate(f"ENCUENTRO\n{hora_enc.strftime('%H:%M:%S')}", 
                                (node['x'], node['y']), xytext=(0, 40),
                                textcoords='offset points', ha='center', fontsize=9,
                                fontweight='bold', color='white', bbox=dict(boxstyle="round", fc="red"))
                    st.success(f"🎊 ¡Encuentro detectado a las {hora_enc.strftime('%H:%M:%S')}!")
                else:
                    st.info("Los recorridos se cruzaron en la zona pero no hubo coincidencia temporal.")

                st.pyplot(fig)
    else:
        st.warning("👈 Dibuja un área en el mapa interactivo para comenzar.")

except Exception as e:
    st.error(f"Error en la simulación: {e}")