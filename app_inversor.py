import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re

st.set_page_config(page_title="Análise de Inversores - Strings", layout="wide")

ARQUIVO_PADRAO = "dados_corrente.xlsx"

# --- CSS PARA IMPRESSÃO ---
def injetar_css_impressao():
    css = """
    <style>
    @media print {
        @page { size: landscape; margin: 1cm; }
        [data-testid="stSidebar"], header[data-testid="stHeader"], 
        [data-testid="stTabs"] [role="tablist"], .stButton { display: none !important; }
        .main .block-container { max-width: 100% !important; width: 100% !important; padding: 0 !important; }
        .stPlotlyChart, .js-plotly-plot { max-width: 100% !important; width: 100% !important; page-break-inside: avoid !important; }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

injetar_css_impressao()

# --- FORMATAÇÃO DE NOMES ---
def extrair_nome_curto(nome_longo):
    nome_str = str(nome_longo)
    match = re.search(r'INV,?\s*0*(\d+).*?string\s*(\d+)', nome_str, flags=re.IGNORECASE)
    if match:
        inv = match.group(1)
        strg = match.group(2).zfill(2)
        return f"{inv}.{strg}"
    return nome_str

# --- CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados(arquivo):
    try:
        if hasattr(arquivo, 'name') and arquivo.name.endswith('.csv'):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
            
        df['Nome do data point'] = df['Nome do data point'].apply(extrair_nome_curto)
        df['Tempo'] = pd.to_datetime(df['Tempo'], dayfirst=True)
        df = df.sort_values(['Nome do data point', 'Tempo'])
        df['Data Apenas'] = df['Tempo'].dt.date
        df['Hora'] = df['Tempo'].dt.strftime('%H:%M')
        return df
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
        return None

# --- FUNÇÕES DE GRÁFICOS ---
def gerar_kpis(df):
    c1, c2, c3, c4 = st.columns(4)
    corrente_max = df['Valor'].max()
    corrente_med = df['Valor'].mean()
    qnt_strings = df['Nome do data point'].nunique()
    string_pico = df.loc[df['Valor'].idxmax(), 'Nome do data point'] if not df.empty else "-"
    
    c1.metric("Total de Strings Ativas", f"{qnt_strings}")
    c2.metric("Corrente Máxima Registrada (A)", f"{corrente_max:.2f}")
    c3.metric("Corrente Média Global (A)", f"{corrente_med:.2f}")
    c4.metric("String com Pico de Corrente", f"{string_pico}")

def plot_linha_corrente(df):
    # 1. Calcular a curva média global do inversor
    df_media_global = df.groupby('Tempo')['Valor'].mean().reset_index()
    
    # 2. Identificar a saúde de cada string (comparando médias diárias)
    # Filtramos o horário nobre (10h às 16h) para uma comparação de saúde mais justa
    df_nobre = df[(df['Tempo'].dt.hour >= 10) & (df['Tempo'].dt.hour <= 16)]
    media_total_inversor = df_nobre['Valor'].mean()
    
    fig = go.Figure()

    # 3. Adicionar as curvas das strings com cores condicionais
    strings = df['Nome do data point'].unique()
    for s in strings:
        df_s = df[df['Nome do data point'] == s]
        df_s_nobre = df_nobre[df_nobre['Nome do data point'] == s]
        
        media_s = df_s_nobre['Valor'].mean()
        # Critério: Verde se >= 90% da média, Vermelho se < 90%
        cor = '#28a745' if media_s >= (0.9 * media_total_inversor) else '#dc3545'
        
        fig.add_trace(go.Scatter(
            x=df_s['Tempo'], y=df_s['Valor'],
            name=f"String {s}",
            line=dict(color=cor, width=1.5),
            opacity=0.7
        ))

    # 4. Adicionar a Curva Média (Destaque)
    fig.add_trace(go.Scatter(
        x=df_media_global['Tempo'], y=df_media_global['Valor'],
        name="MÉDIA GLOBAL",
        line=dict(color='black', width=3, dash='dash'),
        hoverlabel=dict(bgcolor="black")
    ))

    fig.update_layout(
        title="Análise Comparativa de Corrente (A) vs Média do Inversor",
        xaxis_title="Horário",
        yaxis_title="Corrente (A)",
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", y=1.1, xanchor="right", x=1)
    )
    return fig

def plot_boxplot_strings(df):
    df_filtrado = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    fig = px.box(df_filtrado, x='Nome do data point', y='Valor', color='Nome do data point',
                title="Dispersão e Desvios de Corrente (06:00 - 18:00)",
                labels={'Valor': 'Corrente (A)', 'Nome do data point': 'Strings'})
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig.update_xaxes(type='category', categoryorder='category ascending')
    return fig

def plot_barras_acumulado(df):
    df_filtrado = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    df_resumo = df_filtrado.groupby('Nome do data point')['Valor'].sum().reset_index()
    df_resumo = df_resumo.sort_values('Valor', ascending=False)
    
    fig = px.bar(df_resumo, x='Nome do data point', y='Valor', color='Nome do data point',
                title="Soma Acumulada de Corrente por String (06:00 - 18:00)",
                labels={'Valor': 'Soma da Corrente (A)', 'Nome do data point': 'String'})
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig.update_xaxes(type='category')
    return fig

def plot_heatmap_corrente(df):
    if df.empty:
        return go.Figure().update_layout(title="Sem dados suficientes")
    df_pivot = df.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    fig = px.imshow(df_pivot, aspect="auto", color_continuous_scale="Viridis",
                   title="Mapa de Calor: Intensidade de Corrente (A)",
                   labels=dict(x="Horário do Dia", y="String", color="Corrente (A)"))
    fig.update_yaxes(type='category', categoryorder='category descending')
    return fig

# --- INTERFACE ---
st.sidebar.header("📁 Dados do Inversor")
df_bruto = None
arquivo_upload = st.sidebar.file_uploader("Envie o arquivo:", type=["xlsx", "csv"])

if arquivo_upload:
    df_bruto = carregar_dados(arquivo_upload)
elif os.path.exists(ARQUIVO_PADRAO):
    df_bruto = carregar_dados(open(ARQUIVO_PADRAO, "rb"))

if df_bruto is not None:
    datas_disponiveis = df_bruto['Data Apenas'].unique()
    data_sel = st.sidebar.selectbox("Filtre o Dia:", datas_disponiveis) if len(datas_disponiveis) > 1 else datas_disponiveis[0]
    df_filtrado_data = df_bruto[df_bruto['Data Apenas'] == (data_sel if len(datas_disponiveis) > 1 else data_sel)]
    
    strings = df_filtrado_data['Nome do data point'].unique()
    sel_strings = st.sidebar.multiselect("Strings Visíveis:", strings, default=strings)
    
    if sel_strings:
        df_final = df_filtrado_data[df_filtrado_data['Nome do data point'].isin(sel_strings)]
        st.title("⚡ Análise de Corrente por String - Inversor")
        gerar_kpis(df_final)
        
        t1, t2, t3, t4 = st.tabs(["📈 Curvas de Performance", "📦 Boxplot", "📊 Total Acumulado", "🗓️ Heatmap"])
        with t1: 
            st.info("💡 Legenda de Saúde: As curvas em VERDE estão operando com média próxima à do inversor (margem de 10%). As curvas em VERMELHO apresentam desvio negativo superior a 10%.")
            st.plotly_chart(plot_linha_corrente(df_final), use_container_width=True, key="c_linha")
        with t2: st.plotly_chart(plot_boxplot_strings(df_final), use_container_width=True, key="c_box")
        with t3: st.plotly_chart(plot_barras_acumulado(df_final), use_container_width=True, key="c_barra")
        with t4: st.plotly_chart(plot_heatmap_corrente(df_final), use_container_width=True, key="c_heat")
