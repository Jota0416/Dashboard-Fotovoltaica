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
    """
    Transforma 'EQUIP - Inversores 1 - INV, 01 - corrente string 14' em '1.14'
    """
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
        if arquivo.name.endswith('.csv'):
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
    fig = px.line(
        df, x='Tempo', y='Valor', color='Nome do data point',
        title="Curva de Corrente (A) ao longo do tempo",
        labels={'Valor': 'Corrente (A)', 'Tempo': 'Horário'}
    )
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', legend_title_text='Strings')
    return fig

def plot_boxplot_strings(df):
    # Filtro operacional: Exclui dados noturnos para evitar distorção estatística
    df_filtrado = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    
    fig = px.box(
        df_filtrado, x='Nome do data point', y='Valor', color='Nome do data point',
        title="Dispersão e Desvios de Corrente por String (06:00 - 18:00)",
        labels={'Valor': 'Corrente (A)', 'Nome do data point': 'Strings'}
    )
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    return fig

def plot_heatmap_corrente(df):
    if df.empty:
        return go.Figure().update_layout(title="Sem dados suficientes para o Mapa de Calor")
        
    df_pivot = df.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    
    fig = px.imshow(
        df_pivot, 
        aspect="auto", 
        color_continuous_scale="Viridis",
        title="Mapa de Calor: Intensidade de Corrente (A)",
        labels=dict(x="Horário do Dia", y="String", color="Corrente (A)")
    )
    return fig

# --- LÓGICA DE ENTRADA DE DADOS ---
st.sidebar.header("📁 Dados do Inversor")
df_bruto = None

arquivo_upload = st.sidebar.file_uploader("Envie o arquivo (Excel ou CSV):", type=["xlsx", "csv"])

if arquivo_upload:
    df_bruto = carregar_dados(arquivo_upload)
elif os.path.exists(ARQUIVO_PADRAO):
    with open(ARQUIVO_PADRAO, "rb") as f:
        class FakeFile:
            def __init__(self, content, name):
                self.content = content
                self.name = name
            def read(self): return self.content
        df_bruto = carregar_dados(FakeFile(f.read(), ARQUIVO_PADRAO))
    st.sidebar.success(f"✅ Base padrão carregada.")

# --- EXECUÇÃO DO DASHBOARD ---
if df_bruto is not None:
    datas_disponiveis = df_bruto['Data Apenas'].unique()
    if len(datas_disponiveis) > 1:
        data_selecionada = st.sidebar.selectbox("Filtre o Dia:", datas_disponiveis)
        df_filtrado_data = df_bruto[df_bruto['Data Apenas'] == data_selecionada]
    else:
        df_filtrado_data = df_bruto

    strings_disponiveis = df_filtrado_data['Nome do data point'].unique()
    sel_strings = st.sidebar.multiselect("Strings Visíveis:", strings_disponiveis, default=strings_disponiveis)
    
    if sel_strings:
        df_final = df_filtrado_data[df_filtrado_data['Nome do data point'].isin(sel_strings)]
        
        st.title("⚡ Análise de Corrente por String - Inversor")
        st.divider()
        
        gerar_kpis(df_final)
        st.write("")
        
        t1, t2, t3 = st.tabs(["📈 Curvas de Corrente", "📦 Análise de Desvios (Boxplot)", "🗓️ Mapa de Calor"])
        
        with t1:
            st.plotly_chart(plot_linha_corrente(df_final), use_container_width=True, key="c_linha")
        
        with t2:
            st.info("O Boxplot ajuda a identificar strings com subperformance crônica. Os dados noturnos (fora da janela 06h-18h) foram filtrados para não distorcer o cálculo dos quartis.")
            st.plotly_chart(plot_boxplot_strings(df_final), use_container_width=True, key="c_box")
            
        with t3:
            st.info("Cores mais escuras indicam baixa corrente. Quedas verticais (em um mesmo horário para várias strings) indicam sombreamento passageiro.")
            st.plotly_chart(plot_heatmap_corrente(df_final), use_container_width=True, key="c_heat")

else:
    st.title("⚡ Análise de Corrente por String - Inversor")
    st.info("👈 Faça o upload da planilha contendo as colunas 'Nome do data point', 'Tempo' e 'Valor' para visualizar o painel.")
