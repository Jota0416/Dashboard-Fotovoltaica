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

def renderizar_aba_curvas(df):
    df_media_global = df.groupby('Tempo')['Valor'].mean().reset_index()

    # GRÁFICO 1: Panorama Geral
    fig_geral = px.line(df, x='Tempo', y='Valor', color='Nome do data point',
                       title="Panorama Geral: Performance de Todas as Strings",
                       labels={'Valor': 'Corrente (A)', 'Tempo': 'Horário'})
    fig_geral.update_layout(plot_bgcolor='rgba(0,0,0,0)', legend_title_text='Strings')
    st.plotly_chart(fig_geral, use_container_width=True, key="curva_geral")

    st.divider()

    # 2. Configuração da Tolerância e Diagnóstico
    st.subheader("🔍 Diagnóstico de Subperformance (Análise por Janelas Horárias)")
    
    col_slider, _ = st.columns([2, 2])
    with col_slider:
        margem_aceitavel = st.slider(
            "Defina a tolerância aceitável abaixo da média da janela (%):",
            min_value=5, max_value=50, value=10, step=5,
            help="O dia é fatiado em janelas de 1 hora. Se a string ficar abaixo do limite permitido em QUALQUER janela produtiva, ela será sinalizada para análise."
        )
    
    factor = (100 - margem_aceitavel) / 100

    # 3. Filtro de strings (Janelas de 1 em 1 hora, das 6h às 18h)
    strings_abaixo = set() # Usamos um 'set' (conjunto) para não duplicar o nome caso ela falhe em múltiplas horas
    
    for hora in range(6, 19):
        df_hora = df[df['Tempo'].dt.hour == hora]
        if not df_hora.empty:
            media_global_hora = df_hora['Valor'].mean()
            
            # Filtro de ruído: Avalia apenas as horas em que o inversor está de fato gerando (exclui o crepúsculo extremo)
            if media_global_hora > 1.0:
                for s in df_hora['Nome do data point'].unique():
                    media_s_hora = df_hora[df_hora['Nome do data point'] == s]['Valor'].mean()
                    if media_s_hora < (media_global_hora * factor):
                        strings_abaixo.add(s)
    
    strings_abaixo = sorted(list(strings_abaixo))

    # SELEÇÃO DE STRINGS PARA DETALHAMENTO
    if strings_abaixo:
        selecionadas_desvio = st.multiselect(
            f"Strings detectadas com subperformance em pelo menos uma janela horária:",
            options=strings_abaixo,
            default=strings_abaixo
        )
    else:
        st.success(f"✅ Nenhuma string apresentou desvio crítico nas janelas horárias.")
        selecionadas_desvio = []

    # GRÁFICO 2: Análise de Desvios
    fig_desvio = go.Figure()
    fig_desvio.add_trace(go.Scatter(
        x=df_media_global['Tempo'], y=df_media_global['Valor'],
        name="MÉDIA GLOBAL", line=dict(color='black', width=3, dash='dash')
    ))

    for s in selecionadas_desvio:
        df_s = df[df['Nome do data point'] == s]
        fig_desvio.add_trace(go.Scatter(
            x=df_s['Tempo'], y=df_s['Valor'], name=f"String {s}",
            line=dict(width=2), opacity=0.9
        ))

    fig_desvio.update_layout(
        title=f"Análise de Desvios Detalhada (Tolerância: {margem_aceitavel}%)",
        xaxis_title="Horário", yaxis_title="Corrente (A)",
        plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1, xanchor="right", x=1)
    )
    st.plotly_chart(fig_desvio, use_container_width=True, key="curva_desvio")

def plot_boxplot_strings(df):
    df_filtrado = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    fig = px.box(df_filtrado, x='Nome do data point', y='Valor', color='Nome do data point',
                title="Dispersão e Desvios de Corrente (06:00 - 18:00)")
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig.update_xaxes(type='category', categoryorder='category ascending')
    return fig

def plot_barras_acumulado(df):
    df_filtrado = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    df_resumo = df_filtrado.groupby('Nome do data point')['Valor'].sum().reset_index()
    df_resumo = df_resumo.sort_values('Valor', ascending=False)
    fig = px.bar(df_resumo, x='Nome do data point', y='Valor', color='Nome do data point',
                title="Soma Acumulada de Corrente (06:00 - 18:00)")
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig.update_xaxes(type='category')
    return fig

def plot_heatmap_corrente(df):
    if df.empty: return go.Figure()
    df_pivot = df.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    fig = px.imshow(df_pivot, aspect="auto", color_continuous_scale="Viridis",
                   title="Mapa de Calor: Intensidade de Corrente (A)")
    fig.update_yaxes(type='category', categoryorder='category descending')
    return fig

# --- INTERFACE PRINCIPAL ---
st.sidebar.header("📁 Dados do Inversor")
arquivo_upload = st.sidebar.file_uploader("Envie o arquivo:", type=["xlsx", "csv"])

if arquivo_upload:
    df_bruto = carregar_dados(arquivo_upload)
    if df_bruto is not None:
        datas = df_bruto['Data Apenas'].unique()
        data_sel = st.sidebar.selectbox("Filtre o Dia:", datas) if len(datas) > 1 else datas[0]
        df_dia = df_bruto[df_bruto['Data Apenas'] == data_sel]
        
        strings = df_dia['Nome do data point'].unique()
        sel_strings = st.sidebar.multiselect("Strings Visíveis:", strings, default=strings)
        
        if sel_strings:
            df_final = df_dia[df_dia['Nome do data point'].isin(sel_strings)]
            st.title("⚡ Análise de Corrente por String")
            gerar_kpis(df_final)
            
            t1, t2, t3, t4 = st.tabs(["📈 Curvas de Performance", "📦 Boxplot", "📊 Total Acumulado", "🗓️ Heatmap"])
            with t1: renderizar_aba_curvas(df_final)
            with t2: st.plotly_chart(plot_boxplot_strings(df_final), use_container_width=True)
            with t3: st.plotly_chart(plot_barras_acumulado(df_final), use_container_width=True)
            with t4: st.plotly_chart(plot_heatmap_corrente(df_final), use_container_width=True)
