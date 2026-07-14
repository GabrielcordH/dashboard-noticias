"""
app.py — Dashboard "Facções na Imprensa" (protótipo local).

Rodar:
    pip install streamlit plotly pandas
    streamlit run app.py

Fonte de dados: CSV local (3.165 notícias) + 2 GeoJSON.
Quando for para produção, basta trocar `carregar()` por leitura do Google Sheets.
"""

import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from limpeza import carregar_base, CRIMES, PIZZAS_FORTES

CSV = "Questionário_Facções_na_Imprensa.csv"
GEO_BAIRROS = "Bairros_de_Fortaleza.geojson"
GEO_MUN = "geojs-23-mun.json"

st.set_page_config(page_title="Facções na Imprensa — CE", layout="wide")

# ----------------------------------------------------------------------------- #
# Identidade visual INViPS
# ----------------------------------------------------------------------------- #
LARANJA = "#E8730C"       # blocos de destaque / títulos
LARANJA_CLARO = "#F2A05A"
PETROLEO = "#173A48"      # barras e cor base dos gráficos
PETROLEO_CLARO = "#2E6A82"
# escala sequencial dos mapas (claro -> petróleo), no espírito da identidade
ESCALA_MAPA = ["#EAF0F2", "#BCD6DE", "#7FB0BF", "#3E7E93", "#173A48"]
# paleta categórica (facções) partindo das cores da marca
PALETA = [PETROLEO, LARANJA, PETROLEO_CLARO, "#C0553B", "#6E8B95", "#B8860B"]

st.markdown(f"""
<style>
  /* títulos de seção em laranja INViPS */
  h2, h3 {{ color: {PETROLEO} !important; }}
  /* blocos de KPI (métricas) com fundo laranja e texto branco */
  div[data-testid="stMetric"] {{
      background: {LARANJA};
      padding: 16px 20px; border-radius: 10px; color: #fff;
  }}
  div[data-testid="stMetric"] label,
  div[data-testid="stMetric"] div {{ color: #fff !important; }}
  /* barra lateral clarinha */
  section[data-testid="stSidebar"] {{ background: #FAF6F2; }}
  /* rótulos e títulos da barra lateral sempre visíveis */
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] p {{ color: {PETROLEO} !important; }}
  /* divisores discretos */
  hr {{ border-color: #EADFD5; }}
</style>
""", unsafe_allow_html=True)

# tema base aplicado a todos os gráficos Plotly
import plotly.io as pio
pio.templates["invips"] = pio.templates["plotly_white"]
pio.templates["invips"].layout.colorway = PALETA
pio.templates["invips"].layout.font.family = "Arial, sans-serif"
pio.templates.default = "invips"


# ----------------------------------------------------------------------------- #
# Carga (com cache: lê e trata uma vez, compartilha entre usuários)
# ----------------------------------------------------------------------------- #
@st.cache_data(ttl="30m")
def carregar():
    df, longs = carregar_base(CSV, GEO_BAIRROS, GEO_MUN)
    geo_b = json.load(open(GEO_BAIRROS, encoding="utf-8"))
    geo_m = json.load(open(GEO_MUN, encoding="utf-8"))
    return df, longs, geo_b, geo_m


df, longs, geo_b, geo_m = carregar()

# ----------------------------------------------------------------------------- #
# Filtros globais (sidebar)
# ----------------------------------------------------------------------------- #
st.sidebar.title("Filtros")

faccoes_all = sorted({f for fs in df["faccoes"] for f in fs})
crimes_all = list(CRIMES.keys())
veiculos_all = sorted(v for v in df["veiculo"].dropna().unique() if str(v).strip())
anos = df["ano"].dropna().astype(int)
amin, amax = int(anos.min()), int(anos.max())

f_faccao = st.sidebar.multiselect("Facção", faccoes_all, default=[])
f_crime = st.sidebar.multiselect("Tipo de crime", crimes_all, default=[])
f_veiculo = st.sidebar.multiselect("Veículo", veiculos_all, default=[])
f_ano = st.sidebar.slider("Período (ano)", amin, amax, (amin, amax))


def aplica_filtros(base):
    m = base["ano"].between(f_ano[0], f_ano[1]) | base["ano"].isna()
    d = base[m]
    if f_faccao:
        d = d[d["faccoes"].apply(lambda fs: any(x in fs for x in f_faccao))]
    if f_crime:
        d = d[d["crimes"].apply(lambda cs: any(x in cs for x in f_crime))]
    if f_veiculo:
        d = d[d["veiculo"].isin(f_veiculo)]
    return d


dff = aplica_filtros(df)


def filtra_long(long_df):
    d = long_df[long_df["ano"].between(f_ano[0], f_ano[1]) | long_df["ano"].isna()]
    if f_faccao:
        d = d[d["faccoes"].apply(lambda fs: any(x in fs for x in f_faccao))]
    if f_crime:
        d = d[d["crimes"].apply(lambda cs: any(x in cs for x in f_crime))]
    if f_veiculo and "veiculo" in d.columns:
        d = d[d["veiculo"].isin(f_veiculo)]
    return d


# ----------------------------------------------------------------------------- #
# Cabeçalho + KPIs
# ----------------------------------------------------------------------------- #
st.title("Facções na Imprensa — Ceará")
st.caption(f"{len(dff)} notícias no filtro atual (de {len(df)} no total)")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Notícias", len(dff))
k2.metric("Veículos", dff["veiculo"].nunique())
k3.metric("Bairros citados", filtra_long(longs["bairros"])["bairro"].nunique())
k4.metric("Cidades citadas", filtra_long(longs["cidades"])["cidade"].nunique())

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO 1 — Tabela de crimes mencionados
# ----------------------------------------------------------------------------- #
st.subheader("Ocorrências mencionadas nas notícias")
linhas = [{"Crime / fenômeno": k, "Notícias": int(dff["crime__" + k].sum())}
          for k in CRIMES]
tab_crimes = (pd.DataFrame(linhas)
              .sort_values("Notícias", ascending=False)
              .reset_index(drop=True))
st.dataframe(tab_crimes, use_container_width=True, hide_index=True)

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO 2 — Mapas coropléticos (bairro e cidade)
# ----------------------------------------------------------------------------- #
st.subheader("Mapas — contagem de notícias")
mcol1, mcol2 = st.tabs(["Bairros de Fortaleza", "Cidades do Ceará"])

with mcol1:
    cont = (filtra_long(longs["bairros"]).groupby("bairro").size()
            .rename("Notícias").reset_index())
    nomes = [f["properties"]["Nome"] for f in geo_b["features"]]
    base_b = pd.DataFrame({"bairro": nomes}).merge(cont, on="bairro", how="left")
    base_b["Notícias"] = base_b["Notícias"].fillna(0)
    fig = px.choropleth_map(
        base_b, geojson=geo_b, locations="bairro",
        featureidkey="properties.Nome", color="Notícias",
        color_continuous_scale=ESCALA_MAPA, range_color=(0, max(1, base_b["Notícias"].max())),
        map_style="carto-positron", zoom=10.3,
        center={"lat": -3.78, "lon": -38.52}, opacity=0.75,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=560)
    st.plotly_chart(fig, use_container_width=True)

with mcol2:
    cont = (filtra_long(longs["cidades"]).groupby("cidade").size()
            .rename("Notícias").reset_index())
    nomes = [f["properties"]["name"] for f in geo_m["features"]]
    base_c = pd.DataFrame({"cidade": nomes}).merge(cont, on="cidade", how="left")
    base_c["Notícias"] = base_c["Notícias"].fillna(0)
    fig = px.choropleth_map(
        base_c, geojson=geo_m, locations="cidade",
        featureidkey="properties.name", color="Notícias",
        color_continuous_scale=ESCALA_MAPA, range_color=(0, max(1, base_c["Notícias"].max())),
        map_style="carto-positron", zoom=6.2,
        center={"lat": -5.2, "lon": -39.3}, opacity=0.75,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=560)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO 3 e 4 — Barras por ano e por veículo
# ----------------------------------------------------------------------------- #
c1, c2 = st.columns(2)
with c1:
    st.subheader("Notícias por ano")
    por_ano = (dff.dropna(subset=["ano"]).assign(ano=lambda d: d["ano"].astype(int))
               .groupby("ano").size().rename("Notícias").reset_index())
    fig = px.bar(por_ano, x="ano", y="Notícias", text="Notícias", color_discrete_sequence=[PETROLEO])
    fig.update_layout(xaxis_title="", yaxis_title="", height=380,
                      xaxis=dict(dtick=1))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Notícias por veículo")
    por_v = (dff.groupby("veiculo").size().rename("Notícias")
             .reset_index().sort_values("Notícias", ascending=True).tail(15))
    fig = px.bar(por_v, x="Notícias", y="veiculo", orientation="h", text="Notícias", color_discrete_sequence=[PETROLEO])
    fig.update_layout(xaxis_title="", yaxis_title="", height=380)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO — Linha do tempo das facções (ascensão e queda)
# ----------------------------------------------------------------------------- #
st.subheader("Linha do tempo das facções")
st.caption("Ascensão e queda de cada facção na cobertura da imprensa ao longo dos anos. "
           "Reflete protagonismo no *noticiário* (não força real da facção); "
           "anos recentes podem estar super-representados pela data de coleta da base.")

tl1, tl2 = st.columns([3, 1])
with tl2:
    faccoes_plot = st.multiselect(
        "Facções no gráfico", faccoes_all,
        default=[f for f in ["Comando Vermelho", "Guardiões do Estado", "PCC", "Massa (TDN)"]
                 if f in faccoes_all],
    )
    metrica = st.radio("Métrica", ["Contagem", "Share (% do ano)"], index=1)

# usa período + crime dos filtros globais; facção é escolhida localmente acima
base_tl = dff.dropna(subset=["ano"]).copy()
base_tl["ano"] = base_tl["ano"].astype(int)
tot_ano = base_tl.groupby("ano").size()
long_tl = base_tl[["ano", "faccoes"]].explode("faccoes").dropna()
cont = long_tl.groupby(["ano", "faccoes"]).size().rename("n").reset_index()
cont = cont[cont["faccoes"].isin(faccoes_plot)]
if metrica.startswith("Share"):
    cont["valor"] = cont.apply(lambda r: r["n"] / tot_ano.get(r["ano"], 1) * 100, axis=1)
    ylab = "% das notícias do ano"
else:
    cont["valor"] = cont["n"]
    ylab = "nº de notícias"

# share sempre disponível (usado no tamanho das bolhas da linha do tempo)
cont["share"] = cont.apply(lambda r: r["n"] / tot_ano.get(r["ano"], 1) * 100, axis=1)

with tl1:
    if cont.empty:
        st.info("Selecione ao menos uma facção.")
    else:
        fig = px.line(cont, x="ano", y="valor", color="faccoes", markers=True)
        fig.update_layout(xaxis_title="", yaxis_title=ylab, height=430,
                          xaxis=dict(dtick=1), legend_title="")
        st.plotly_chart(fig, use_container_width=True)

# --- Linha do tempo propriamente dita: uma bolha por (ano, facção), tamanho = share ---
if not cont.empty:
    st.markdown("**Linha do tempo — surgimento, auge e queda** "
                "(tamanho da bolha = % das notícias do ano)")
    ordem = [f for f in faccoes_plot if f in cont["faccoes"].unique()]
    figb = px.scatter(
        cont, x="ano", y="faccoes", size="share", color="faccoes",
        size_max=42, category_orders={"faccoes": ordem},
        custom_data=["n", "share"],
    )
    figb.update_traces(hovertemplate="%{y} — %{x}<br>%{customdata[0]} notícias "
                                     "(%{customdata[1]:.1f}% do ano)<extra></extra>")
    figb.update_layout(xaxis_title="", yaxis_title="", height=90 + 60 * max(1, len(ordem)),
                       xaxis=dict(dtick=1), showlegend=False)
    st.plotly_chart(figb, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO 5 — 5 pizzas fortes + barra consolidada
# ----------------------------------------------------------------------------- #
st.subheader("Categorização das notícias")
cols = st.columns(5)
for col, rotulo in zip(cols, PIZZAS_FORTES):
    n = len(dff)
    sim = int(dff["crime__" + rotulo].sum())
    fig = go.Figure(go.Pie(
        labels=["Sim", "Não"], values=[sim, n - sim], hole=0.45,
        marker_colors=[LARANJA, "#E3DAD1"], textinfo="percent", sort=False,
    ))
    fig.update_layout(title=dict(text=rotulo, font=dict(size=13)),
                      showlegend=False, margin=dict(l=4, r=4, t=40, b=4), height=230)
    col.plotly_chart(fig, use_container_width=True)

st.markdown("**Todos os fenômenos retratados (% das notícias do filtro)**")
linhas = [{"Fenômeno": k, "%": dff["crime__" + k].mean() * 100} for k in CRIMES]
barra = pd.DataFrame(linhas).sort_values("%", ascending=True)
fig = px.bar(barra, x="%", y="Fenômeno", orientation="h", color_discrete_sequence=[LARANJA],
             text=barra["%"].map(lambda v: f"{v:.1f}%"))
fig.update_layout(xaxis_title="", yaxis_title="", height=560)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------- #
# BLOCO 6 — Tabela de notícias com busca no resumo
# ----------------------------------------------------------------------------- #
st.subheader("Notícias")
termo = st.text_input("Buscar termo no resumo", "")
tabela = dff.copy()
if termo.strip():
    tabela = tabela[tabela["resumo"].str.contains(termo.strip(), case=False, na=False)]

vis = tabela[["data", "veiculo", "titulo", "resumo", "link"]].copy()
vis = vis.rename(columns={"data": "Data", "veiculo": "Veículo",
                          "titulo": "Título", "resumo": "Resumo", "link": "Link"})
vis["Data"] = vis["Data"].dt.strftime("%d/%m/%Y")
st.caption(f"{len(vis)} notícias")
st.dataframe(
    vis, use_container_width=True, hide_index=True,
    column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")},
)
