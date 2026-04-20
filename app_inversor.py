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
            try:
                df = pd.read_csv(arquivo, sep=';', decimal=',')
            except:
                arquivo.seek(0)
                df = pd.read_csv(arquivo, sep=',')
        else:
            df = pd.read_excel(arquivo)
            
        df['Nome do data point'] = df['Nome do data point'].apply(extrair_nome_curto)
        df['Tempo'] = pd.to_datetime(df['Tempo'], dayfirst=True)
        df = df.sort_values(['Nome do data point', 'Tempo'])
        df['Data Apenas'] = df['Tempo'].dt.date
        df['Hora'] = df['Tempo'].dt.strftime('%H:%M')
        df['MesAno'] = df['Tempo'].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
        return None

# --- FUNÇÕES DE GRÁFICOS (MENSAL) ---
def renderizar_aba_mensal(df_mes):
    st.header(f"📊 Relatório Consolidado Mensal")
    
    # KPIs Mensais
    c1, c2, c3, c4 = st.columns(4)
    total_ah = df_mes[(df_mes['Tempo'].dt.hour >= 6) & (df_mes['Tempo'].dt.hour <= 18)]['Valor'].sum()
    media_mensal = df_mes['Valor'].mean()
    pico_mensal = df_mes['Valor'].max()
    dias_analisados = df_mes['Data Apenas'].nunique()
    
    c1.metric("Dias Processados", dias_analisados)
    c2.metric("Volume Acumulado (Ah)", f"{total_ah:.2f}")
    c3.metric("Média de Corrente (A)", f"{media_mensal:.2f}")
    c4.metric("Pico de Corrente no Mês (A)", f"{pico_mensal:.2f}")
    
    st.divider()

    col1, col2 = st.columns(2)
    
    with col1:
        # Curva Média Mensal (Dia Típico) - Com Seletor de Destaque
        df_mes['Hora_Bloco'] = df_mes['Tempo'].dt.floor('15min').dt.strftime('%H:%M')
        df_tipico = df_mes.groupby(['Hora_Bloco', 'Nome do data point'])['Valor'].mean().reset_index()
        df_tipico_global = df_mes.groupby('Hora_Bloco')['Valor'].mean().reset_index()
        
        # Adiciona um seletor rápido para destacar uma string específica
        lista_strings = ["Nenhuma"] + sorted(df_tipico['Nome do data point'].unique())
        destaque = st.selectbox("Selecione uma String para destacar na curva:", lista_strings)
        
        fig_tipico = go.Figure()
        
        # 1. Desenha as linhas de FUNDO (Strings não destacadas)
        for s in df_tipico['Nome do data point'].unique():
            if s != destaque:
                df_s = df_tipico[df_tipico['Nome do data point'] == s]
                fig_tipico.add_trace(go.Scatter(
                    x=df_s['Hora_Bloco'], y=df_s['Valor'],
                    mode='lines',
                    line=dict(color='rgba(150, 150, 150, 0.4)', width=1.5), # Cinza com transparência
                    name=s,
                    showlegend=False,
                    hovertemplate="<b>" + s + "</b><br>Corrente: %{y:.2f} A<extra></extra>"
                ))
        
        # 2. Desenha a linha DESTACADA (Se alguma for selecionada)
        if destaque != "Nenhuma":
            df_destaque = df_tipico[df_tipico['Nome do data point'] == destaque]
            fig_tipico.add_trace(go.Scatter(
                x=df_destaque['Hora_Bloco'], y=df_destaque['Valor'],
                mode='lines',
                line=dict(color='orange', width=4), # Laranja, grossa e sem transparência
                name=f"Destaque: {destaque}",
                hovertemplate="<b>%{name}</b><br>Corrente: %{y:.2f} A<extra></extra>"
            ))
            
        # 3. Desenha a MÉDIA GLOBAL (Por último para ficar por cima de todas)
        fig_tipico.add_trace(go.Scatter(
            x=df_tipico_global['Hora_Bloco'], y=df_tipico_global['Valor'],
            mode='lines',
            line=dict(color='black', width=3.5),
            name="Média Global",
            hovertemplate="<b>MÉDIA GLOBAL</b><br>Corrente: %{y:.2f} A<extra></extra>"
        ))
        
        fig_tipico.update_layout(
            title="Dia Típico: Comportamento Médio (Janelas de 15 min)",
            xaxis_title="Horário",
            yaxis_title="Corrente (A)",
            plot_bgcolor='rgba(0,0,0,0)',
            hovermode="closest",
            legend=dict(orientation="h", y=1.15, xanchor="right", x=1) # Coloca a legenda em cima
        )
        st.plotly_chart(fig_tipico, use_container_width=True)
        
    with col2:
        # Boxplot Mensal - Monocromático Laranja
        df_box_mes = df_mes[(df_mes['Tempo'].dt.hour >= 6) & (df_mes['Tempo'].dt.hour <= 18)]
        fig_box_mes = px.box(df_box_mes, x='Nome do data point', y='Valor',
                            title="Dispersão Mensal de Corrente (06h-18h)",
                            color_discrete_sequence=['orange'])
        fig_box_mes.update_xaxes(type='category')
        st.plotly_chart(fig_box_mes, use_container_width=True)

        # Estabilidade Mensal (Volatilidade Acumulada) - Monocromático Laranja
        df_mes_sorted = df_mes.sort_values(['Nome do data point', 'Tempo'])
        df_mes_sorted['Variacao'] = df_mes_sorted.groupby('Nome do data point')['Valor'].diff().abs()
        df_vol_mes = df_mes_sorted.groupby('Nome do data point')['Variacao'].sum().reset_index()
        fig_vol_mes = px.bar(df_vol_mes.sort_values('Variacao', ascending=False), 
                            x='Nome do data point', y='Variacao',
                            title="Índice de Volatilidade Acumulado no Mês",
                            color_discrete_sequence=['orange'])
        fig_vol_mes.update_xaxes(type='category')
        st.plotly_chart(fig_vol_mes, use_container_width=True)

    st.divider()
    # Heatmap Médio Mensal
    st.subheader("🗓️ Intensidade Média Horária (Heatmap Mensal)")
    df_pivot_mes = df_mes.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    fig_heat_mes = px.imshow(df_pivot_mes, aspect="auto", color_continuous_scale="Viridis")
    fig_heat_mes.update_yaxes(type='category')
    st.plotly_chart(fig_heat_mes, use_container_width=True)

# --- FUNÇÕES ORIGINAIS DIÁRIAS (MANTIDAS) ---
def renderizar_aba_curvas(df):
    df_media_global = df.groupby('Tempo')['Valor'].mean().reset_index()
    fig_geral = px.line(df, x='Tempo', y='Valor', color='Nome do data point', title="Panorama Geral: Performance de Todas as Strings")
    st.plotly_chart(fig_geral, use_container_width=True)
    st.divider()
    st.subheader("🔍 Diagnóstico de Subperformance")
    margem = st.slider("Tolerância aceitável (%):", 5, 50, 10)
    df_produtivo = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    media_global = df_produtivo['Valor'].mean()
    strings_abaixo = sorted([s for s in df_produtivo['Nome do data point'].unique() if df_produtivo[df_produtivo['Nome do data point']==s]['Valor'].mean() < (media_global * (100-margem)/100)])
    selecionadas = st.multiselect("Strings com desvio crítico:", strings_abaixo, default=strings_abaixo)
    fig_desvio = go.Figure()
    fig_desvio.add_trace(go.Scatter(x=df_media_global['Tempo'], y=df_media_global['Valor'], name="MÉDIA GLOBAL", line=dict(color='black', width=3, dash='dash')))
    for s in selecionadas:
        df_s = df[df['Nome do data point'] == s]
        fig_desvio.add_trace(go.Scatter(x=df_s['Tempo'], y=df_s['Valor'], name=f"String {s}", line=dict(width=2)))
    st.plotly_chart(fig_desvio, use_container_width=True)

def plot_boxplot_strings(df):
    fig = px.box(df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)], x='Nome do data point', y='Valor', color='Nome do data point', title="Dispersão de Corrente (06h-18h)")
    fig.update_xaxes(type='category', categoryorder='category ascending')
    return fig

def plot_barras_acumulado(df):
    df_res = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)].groupby('Nome do data point')['Valor'].sum().reset_index()
    fig = px.bar(df_res.sort_values('Valor', ascending=False), x='Nome do data point', y='Valor', color='Nome do data point', title="Soma Acumulada (06h-18h)")
    fig.update_xaxes(type='category')
    return fig

def plot_heatmap_corrente(df):
    df_p = df.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    fig = px.imshow(df_p, aspect="auto", color_continuous_scale="Viridis", title="Intensidade de Corrente (A)")
    fig.update_yaxes(type='category')
    return fig

def plot_periodo_ativo(df):
    df_a = df[df['Valor'] >= 0.5]
    if df_a.empty: return go.Figure()
    res = df_a.groupby('Nome do data point').agg(Inicio=('Tempo', 'min'), Fim=('Tempo', 'max')).reset_index()
    fig = px.timeline(res, x_start="Inicio", x_end="Fim", y="Nome do data point", color="Nome do data point", title="Período Produtivo")
    fig.update_yaxes(autorange="reversed", type='category')
    return fig

def plot_estabilidade(df):
    df_s = df.sort_values(['Nome do data point', 'Tempo'])
    df_s['Var'] = df_s.groupby('Nome do data point')['Valor'].diff().abs()
    df_v = df_s.groupby('Nome do data point')['Var'].sum().reset_index()
    media_v = df_v['Var'].mean()
    fig = px.bar(df_v.sort_values('Var', ascending=False), x='Nome do data point', y='Var', color='Nome do data point', title="Índice de Volatilidade")
    fig.add_hline(y=media_v, line_dash="dash", line_color="black", annotation_text=f"Média: {media_v:.2f} A")
    fig.update_xaxes(type='category')
    return fig

# --- INTERFACE PRINCIPAL ---
st.sidebar.header("📁 Gestão de Dados")
arquivo_upload = st.sidebar.file_uploader("Carregar planilha:", type=["xlsx", "csv"])

if arquivo_upload:
    df_bruto = carregar_dados(arquivo_upload)
    if df_bruto is not None:
        meses = sorted(df_bruto['MesAno'].unique(), reverse=True)
        mes_sel = st.sidebar.selectbox("Selecione o Mês para Relatório:", meses)
        df_mes = df_bruto[df_bruto['MesAno'] == mes_sel]
        
        datas = sorted(df_mes['Data Apenas'].unique(), reverse=True)
        data_sel = st.sidebar.selectbox("Ou selecione um Dia Específico:", datas)
        df_dia = df_mes[df_mes['Data Apenas'] == data_sel]
        
        st.sidebar.divider()
        strings = sorted(df_bruto['Nome do data point'].unique())
        sel_strings = st.sidebar.multiselect("Filtrar Strings:", strings, default=strings)
        
        if sel_strings:
            df_final_dia = df_dia[df_dia['Nome do data point'].isin(sel_strings)]
            df_final_mes = df_mes[df_mes['Nome do data point'].isin(sel_strings)]
            
            st.title(f"⚡ Dashboard Inversor - {mes_sel}")
            
            tabs = st.tabs(["📊 Relatório Mensal", "📈 Curvas Diárias", "📦 Boxplot", "📊 Acumulado", "🗓️ Heatmap", "☀️ Atividade", "⚡ Estabilidade"])
            
            with tabs[0]: renderizar_aba_mensal(df_final_mes)
            with tabs[1]: renderizar_aba_curvas(df_final_dia)
            with tabs[2]: st.plotly_chart(plot_boxplot_strings(df_final_dia), use_container_width=True)
            with tabs[3]: st.plotly_chart(plot_barras_acumulado(df_final_dia), use_container_width=True)
            with tabs[4]: st.plotly_chart(plot_heatmap_corrente(df_final_dia), use_container_width=True)
            with tabs[5]: st.plotly_chart(plot_periodo_ativo(df_final_dia), use_container_width=True)
            with tabs[6]: st.plotly_chart(plot_estabilidade(df_final_dia), use_container_width=True)
