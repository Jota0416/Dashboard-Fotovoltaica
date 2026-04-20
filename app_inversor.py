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
    st.subheader("🔍 Diagnóstico de Subperformance (Média Diária)")
    
    col_slider, _ = st.columns([2, 2])
    with col_slider:
        margem_aceitavel = st.slider(
            "Defina a tolerância aceitável abaixo da média diária (%):",
            min_value=5, max_value=50, value=10, step=5,
            help="Se a média de geração da string ao longo de todo o dia ficar abaixo do limite tolerado, ela será sinalizada."
        )
    
    factor = (100 - margem_aceitavel) / 100

    # 3. Filtro de strings (Média do dia inteiro)
    df_produtivo = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    strings_abaixo = []
    
    if not df_produtivo.empty:
        media_global_dia = df_produtivo['Valor'].mean()
        
        if media_global_dia > 0:
            for s in df_produtivo['Nome do data point'].unique():
                media_s = df_produtivo[df_produtivo['Nome do data point'] == s]['Valor'].mean()
                if media_s < (media_global_dia * factor):
                    strings_abaixo.append(s)
    
    strings_abaixo = sorted(strings_abaixo)

    # SELEÇÃO DE STRINGS PARA DETALHAMENTO
    if strings_abaixo:
        selecionadas_desvio = st.multiselect(
            f"Strings detectadas com subperformance na média diária:",
            options=strings_abaixo,
            default=strings_abaixo
        )
    else:
        st.success(f"✅ Nenhuma string apresentou desvio crítico na média do dia.")
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

def plot_periodo_ativo(df):
    # Considera ativa a string gerando mais de 0.5A
    df_ativo = df[df['Valor'] >= 0.5]
    if df_ativo.empty:
        return go.Figure().update_layout(title="Nenhuma string atingiu o limiar de 0.5A")

    # Identifica o primeiro e o último registro de geração no dia
    resumo = df_ativo.groupby('Nome do data point').agg(
        Inicio=('Tempo', 'min'),
        Fim=('Tempo', 'max')
    ).reset_index()

    fig = px.timeline(
        resumo, x_start="Inicio", x_end="Fim", y="Nome do data point", color="Nome do data point",
        title="Período Produtivo das Strings (Nascer e Pôr do Sol do Inversor)",
        labels={"Nome do data point": "String"}
    )
    # Inverte o eixo Y para ordem crescente de strings (de cima para baixo)
    fig.update_yaxes(autorange="reversed", type='category')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    return fig

def plot_estabilidade(df):
    # Calcula a flutuação somando o desvio absoluto entre as medições sequenciais
    df_sorted = df.sort_values(['Nome do data point', 'Tempo'])
    df_sorted['Variacao'] = df_sorted.groupby('Nome do data point')['Valor'].diff().abs()
    
    df_volatilidade = df_sorted.groupby('Nome do data point')['Variacao'].sum().reset_index()
    df_volatilidade = df_volatilidade.sort_values('Variacao', ascending=False)

    fig = px.bar(
        df_volatilidade, x='Nome do data point', y='Variacao', color='Nome do data point',
        title="Índice de Volatilidade (Soma das Flutuações de Corrente)",
        labels={'Variacao': 'Soma das Flutuações (A)', 'Nome do data point': 'String'}
    )
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig.update_xaxes(type='category')
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
            
            t1, t2, t3, t4, t5, t6 = st.tabs([
                "📈 Curvas de Performance", "📦 Boxplot", "📊 Total Acumulado", 
                "🗓️ Heatmap", "☀️ Período Ativo", "⚡ Estabilidade"
            ])
            with t1: renderizar_aba_curvas(df_final)
            with t2: st.plotly_chart(plot_boxplot_strings(df_final), use_container_width=True)
            with t3: st.plotly_chart(plot_barras_acumulado(df_final), use_container_width=True)
            with t4: st.plotly_chart(plot_heatmap_corrente(df_final), use_container_width=True)
            
            with t5: 
                st.info("O Diagrama de Período Ativo mapeia o horário exato de partida e desligamento de cada string (limiar > 0.5A). Um atraso isolado na partida evidencia sombreamento de horizonte no amanhecer ou entardecer.")
                st.plotly_chart(plot_periodo_ativo(df_final), use_container_width=True)
                
            with t6: 
                st.info("O Índice de Volatilidade ranqueia as strings baseando-se na soma de todas as variações abruptas de corrente. Barras significativamente maiores que a média são assinaturas de intermitência física, como conectores soltos, diodos defeituosos ou falhas de isolamento.")
                st.plotly_chart(plot_estabilidade(df_final), use_container_width=True)
