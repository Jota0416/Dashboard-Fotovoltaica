import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="Dashboard Analítico O&M", layout="wide")

# --- CONFIGURAÇÃO DO ARQUIVO PADRÃO ---
ARQUIVO_PADRAO = "dados_solar.xlsx"

# --- CSS PARA IMPRESSÃO ---
def injetar_css_impressao():
    css = """
    <style>
    @media print {
        @page { size: landscape; margin: 1cm; }
        [data-testid="stSidebar"], header[data-testid="stHeader"], 
        [data-testid="stTabs"] [role="tablist"], .stButton, .stAlert { display: none !important; }
        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 0 !important; }
        .stPlotlyChart, .js-plotly-plot, .plotly.plotly-graph-div { max-width: 100% !important; width: 100% !important; }
        [data-testid="stElementContainer"] { page-break-inside: avoid !important; break-inside: avoid !important; margin-bottom: 15px !important; }
        h1, h2, h3 { page-break-after: avoid !important; break-after: avoid !important; }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

injetar_css_impressao()

# --- CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados_excel(arquivo):
    try:
        xls = pd.ExcelFile(arquivo)
        df_m = pd.read_excel(xls, sheet_name='Mensal')
        df_d = pd.read_excel(xls, sheet_name='Diario')
        df_d['Data'] = pd.to_datetime(df_d['Data'])
        df_d['Dia'] = df_d['Data'].dt.day
        df_d = df_d.sort_values(['Usina', 'Data'])
        df_d['Geração Acumulada'] = df_d.groupby('Usina')['Geração (MWh)'].cumsum()
        metas = df_m.set_index('Usina')['Meta (MWh)'].to_dict()
        total_dias = df_d['Dia'].max()
        df_d['Meta Diária'] = df_d['Usina'].map(metas) / total_dias
        df_d['Meta Acumulada'] = df_d.groupby('Usina')['Meta Diária'].cumsum()
        return df_m, df_d
    except Exception as e:
        st.error(f"Erro ao processar Excel: {e}")
        return None, None

# --- FUNÇÕES DE GRÁFICOS ---
def gerar_kpis(df_m):
    c1, c2, c3 = st.columns(3)
    gen_total = df_m['Geração Real (MWh)'].sum()
    meta_total = df_m['Meta (MWh)'].sum()
    epi = (gen_total / meta_total) * 100 if meta_total > 0 else 0
    c1.metric("Geração Total (MWh)", f"{gen_total:.1f}")
    c2.metric("Meta Total (MWh)", f"{meta_total:.1f}")
    c3.metric("EPI (%)", f"{epi:.1f}%")

def plot_curva_s_global(df_d):
    df_global = df_d.groupby('Data').agg({'Geração Acumulada': 'sum', 'Meta Acumulada': 'sum'}).reset_index()
    usinas_inclusas = ", ".join(df_d['Usina'].unique())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_global['Data'], y=df_global['Meta Acumulada'], name='Meta Esperada', line=dict(color='#A5A5A5', width=2, dash='dash')))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Real (Na Meta)', line=dict(color='#1F4E79', width=3)))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Real (Até -10%)', line=dict(color='#FFC000', width=3)))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', name='Real (> -10%)', line=dict(color='#C00000', width=3)))
    
    datas, geracao, meta = df_global['Data'].tolist(), df_global['Geração Acumulada'].tolist(), df_global['Meta Acumulada'].tolist()
    for i in range(1, len(df_global)):
        ratio = geracao[i] / meta[i] if meta[i] > 0 else 1.0
        cor = '#1F4E79' if ratio >= 1.0 else ('#FFC000' if ratio >= 0.9 else '#C00000')
        fig.add_trace(go.Scatter(x=[datas[i-1], datas[i]], y=[geracao[i-1], geracao[i]], mode='lines', line=dict(color=cor, width=3), showlegend=False, hoverinfo='skip'))
    
    fig.add_trace(go.Scatter(x=datas, y=geracao, mode='lines', line=dict(color='rgba(0,0,0,0)'), showlegend=False, name='Geração', hovertemplate='%{y:.1f} MWh<extra></extra>'))
    fig.update_layout(title=f"Curva S: Comparativo Global (Consolidado)<br><sup>Usinas: {usinas_inclusas}</sup>", plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1, xanchor="right", x=1))
    return fig

def renderizar_curvas_s_individuais(df_d, usinas, key_pref):
    cores_paleta = px.colors.qualitative.Bold
    for i, usina in enumerate(usinas):
        df_u = df_d[df_d['Usina'] == usina]
        cor = cores_paleta[i % len(cores_paleta)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_u['Data'], y=df_u['Geração Acumulada'], name='Geração Real', line=dict(color=cor, width=3)))
        fig.add_trace(go.Scatter(x=df_u['Data'], y=df_u['Meta Acumulada'], name='Meta Esperada', line=dict(color='#A5A5A5', width=2, dash='dash')))
        fig.update_layout(title=f"Curva S: {usina}", plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_pref}_{usina}")

def plot_heatmap_segmentado(df_d, key_pref):
    gps = [(['UFV Pôr do Sol', 'UFV Lago'], "Blues", "Grupo 1"), (['UFV Salta Fogo 1', 'UFV Salta Fogo 2'], "Greens", "Grupo 2")]
    for usinas, cor, nome in gps:
        df_g = df_d[df_d['Usina'].isin(usinas)]
        if not df_g.empty:
            st.plotly_chart(px.imshow(df_g.pivot(index='Usina', columns='Dia', values='Geração (MWh)'), text_auto=".1f", color_continuous_scale=cor, title=f"Intensidade Diária: {nome}"), use_container_width=True, key=f"{key_pref}_{nome}")

def plot_roscas(df_m, key_pref):
    cols = st.columns(len(df_m))
    for idx, row in df_m.iterrows():
        p_irr, p_clip, p_rede = row.get('Irradiação (Perda %)', 0), row.get('Clipping (Perda %)', 0), row.get('Indisponibilidade da Rede (%)', 0)
        labels, valores, cores = ['Gerado'], [100-(p_irr+p_clip+p_rede)], ['#1F4E79']
        for l, v, c in zip(['Irradiação', 'Clipping', 'Rede'], [p_irr, p_clip, p_rede], ['#C00000', '#F4B084', '#7F7F7F']):
            if v > 0: labels.append(l); valores.append(v); cores.append(c)
        fig = go.Figure(data=[go.Pie(labels=labels, values=valores, hole=.4, marker_colors=cores)])
        fig.update_layout(title_text=row['Usina'], legend=dict(orientation="h", y=-0.1, xanchor="center", x=0.5), margin=dict(t=50, b=100, l=10, r=10))
        with cols[idx % len(cols)]: st.plotly_chart(fig, use_container_width=True, key=f"{key_pref}_{idx}")

# --- LÓGICA DE ENTRADA DE DADOS ---
st.sidebar.header("📁 Dados do Portfólio")
df_m, df_d = None, None

if os.path.exists(ARQUIVO_PADRAO):
    df_m, df_d = carregar_dados_excel(ARQUIVO_PADRAO)
    st.sidebar.success(f"✅ Base de dados '{ARQUIVO_PADRAO}' carregada.")
    if st.sidebar.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.rerun()

arquivo_upload = st.sidebar.file_uploader("Ou envie um novo arquivo Excel:", type=["xlsx"])
if arquivo_upload:
    df_m, df_d = carregar_dados_excel(arquivo_upload)

# --- EXECUÇÃO DO DASHBOARD ---
if df_m is not None:
    sel = st.sidebar.multiselect("Usinas Ativas:", df_m['Usina'].unique(), default=df_m['Usina'].unique())
    if sel:
        df_mf, df_df = df_m[df_m['Usina'].isin(sel)], df_d[df_d['Usina'].isin(sel)]
        st.title("☀️ Dashboard Analítico - Portfólio Solar")
        t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📈 Diária", "📊 Curva S", "📦 Boxplot", "🔍 Perdas", "🎯 Dispersão", "🗓️ Heatmap", "📑 Relatório"])
        
        with t1: 
            gerar_kpis(df_mf)
            st.plotly_chart(px.line(df_df, x='Data', y='Geração (MWh)', color='Usina', title="Geração Diária").update_layout(plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True, key="aba_linha")
        with t2: 
            st.plotly_chart(plot_curva_s_global(df_df), use_container_width=True, key="global_s")
            st.divider()
            st.subheader("Análise Individualizada")
            renderizar_curvas_s_individuais(df_df, sel, "aba_s")
        with t3: 
            st.plotly_chart(px.box(df_df, x='Usina', y='Geração (MWh)', color='Usina', title="Variabilidade").update_layout(plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True, key="aba_box")
        with t4: 
            st.subheader("Decomposição de Perdas (%)")
            plot_roscas(df_mf, "r4")
        with t5: 
            st.plotly_chart(px.scatter(df_df, x="Irradiação (kWh/m²)", y="Geração (MWh)", color="Usina", trendline="ols", title="Eficiência").update_layout(plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True, key="aba_scat")
        with t6:
            min_d, max_d = int(df_df['Dia'].min()), int(df_df['Dia'].max())
            intervalo = st.slider("Intervalo de dias:", min_d, max_d, (min_d, max_d))
            plot_heatmap_segmentado(df_df[(df_df['Dia'] >= intervalo[0]) & (df_df['Dia'] <= intervalo[1])], "aba_heat")
        with t7:
            st.subheader("Relatório Consolidado")
            if st.button("🖨️ Gerar PDF"): components.html("<script>setTimeout(function(){window.parent.print();}, 500);</script>", height=0)
            st.divider()
            gerar_kpis(df_mf)
            st.plotly_chart(plot_curva_s_global(df_df), use_container_width=True, key="rel_global_s")
            st.subheader("Detalhamento por Unidade")
            renderizar_curvas_s_individuais(df_df, sel, "rel_ind_s")
            st.plotly_chart(px.box(df_df, x='Usina', y='Geração (MWh)', color='Usina', title="Variabilidade").update_layout(plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True, key="rel_box")
            plot_heatmap_segmentado(df_df, "rel_heat")
            st.subheader("Balanço de Perdas")
            plot_roscas(df_mf, "rel_r4")
else:
    st.title("☀️ Dashboard Analítico - Portfólio Solar")
    st.info("ℹ️ Para iniciar, envie o arquivo Excel pelo menu lateral ou certifique-se de que 'dados_solar.xlsx' está no repositório.")
