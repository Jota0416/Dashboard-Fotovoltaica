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

# --- CARREGAMENTO DE DADOS COM TRATAMENTO DE DELIMITADORES ---
@st.cache_data
def carregar_dados(arquivo):
    try:
        if hasattr(arquivo, 'name') and arquivo.name.endswith('.csv'):
            try:
                # Padrão Brasileiro (sep ; decimal ,)
                df = pd.read_csv(arquivo, sep=';', decimal=',')
            except:
                arquivo.seek(0)
                # Padrão Internacional (sep , decimal .)
                df = pd.read_csv(arquivo, sep=',')
        else:
            df = pd.read_excel(arquivo)
            
        # Garante que o nome da string seja tratado exclusivamente como texto para evitar eixos em branco
        df['Nome do data point'] = df['Nome do data point'].apply(extrair_nome_curto).astype(str)
        df['Tempo'] = pd.to_datetime(df['Tempo'], dayfirst=True)
        df = df.sort_values(['Nome do data point', 'Tempo'])
        df['Data Apenas'] = df['Tempo'].dt.date
        df['Hora'] = df['Tempo'].dt.strftime('%H:%M')
        df['MesAno'] = df['Tempo'].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
        return None

# --- KPIS ---
def gerar_kpis(df):
    c1, c2, c3, c4 = st.columns(4)
    corrente_max = df['Valor'].max()
    corrente_med = df['Valor'].mean()
    qnt_strings = df['Nome do data point'].nunique()
    string_pico = df.loc[df['Valor'].idxmax(), 'Nome do data point'] if not df.empty else "-"
    
    c1.metric("Strings Ativas", f"{qnt_strings}")
    c2.metric("Corrente Máxima (A)", f"{corrente_max:.2f}")
    c3.metric("Média Global (A)", f"{corrente_med:.2f}")
    c4.metric("String de Pico", f"{string_pico}")

# --- ABA MENSAL ---
def renderizar_aba_mensal(df_mes):
    st.header(f"📊 Relatório Consolidado Mensal")
    
    c1, c2, c3, c4 = st.columns(4)
    df_prod = df_mes[(df_mes['Tempo'].dt.hour >= 6) & (df_mes['Tempo'].dt.hour <= 18)]
    total_ah = df_prod['Valor'].sum()
    c1.metric("Dias Processados", df_mes['Data Apenas'].nunique())
    c2.metric("Acumulado (Ah)", f"{total_ah:.2f}")
    c3.metric("Média Mensal (A)", f"{df_mes['Valor'].mean():.2f}")
    c4.metric("Pico Mensal (A)", f"{df_mes['Valor'].max():.2f}")
    
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico Dia Típico com Destaque
        df_mes['Hora_Bloco'] = df_mes['Tempo'].dt.floor('15min').dt.strftime('%H:%M')
        df_tipico = df_mes.groupby(['Hora_Bloco', 'Nome do data point'])['Valor'].mean().reset_index()
        df_global = df_mes.groupby('Hora_Bloco')['Valor'].mean().reset_index()
        
        lista_strings = ["Nenhuma"] + sorted(df_tipico['Nome do data point'].unique())
        destaque = st.selectbox("Destacar String no gráfico:", lista_strings)
        
        fig_tipico = go.Figure()
        for s in df_tipico['Nome do data point'].unique():
            if s != destaque:
                df_s = df_tipico[df_tipico['Nome do data point'] == s]
                fig_tipico.add_trace(go.Scatter(
                    x=df_s['Hora_Bloco'], y=df_s['Valor'], mode='lines',
                    line=dict(color='rgba(150, 150, 150, 0.4)', width=1.5),
                    name=s, showlegend=False, hovertemplate="<b>"+s+"</b><br>%{y:.2f} A<extra></extra>"
                ))
        
        if destaque != "Nenhuma":
            df_d = df_tipico[df_tipico['Nome do data point'] == destaque]
            fig_tipico.add_trace(go.Scatter(
                x=df_d['Hora_Bloco'], y=df_d['Valor'], mode='lines',
                line=dict(color='orange', width=4), name=f"Destaque: {destaque}"
            ))
            
        fig_tipico.add_trace(go.Scatter(
            x=df_global['Hora_Bloco'], y=df_global['Valor'], mode='lines',
            line=dict(color='black', width=3, dash='dash'), name="Média Global"
        ))
        
        fig_tipico.update_layout(title="Dia Típico (Média 15min)", plot_bgcolor='rgba(0,0,0,0)', hovermode="closest")
        st.plotly_chart(fig_tipico, use_container_width=True)

        # Acumulado Mensal Laranja
        df_acum = df_prod.groupby('Nome do data point')['Valor'].sum().reset_index()
        fig_bar = px.bar(df_acum.sort_values('Valor', ascending=False), x='Nome do data point', y='Valor',
                        title="Acumulado Mensal (Ah)", color_discrete_sequence=['orange'])
        fig_bar.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_acum['Nome do data point'].unique()))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        # Boxplot Laranja
        fig_box = px.box(df_prod, x='Nome do data point', y='Valor', title="Dispersão Mensal", color_discrete_sequence=['orange'])
        fig_box.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_prod['Nome do data point'].unique()))
        st.plotly_chart(fig_box, use_container_width=True)

        # Estabilidade Laranja
        df_s = df_mes.sort_values(['Nome do data point', 'Tempo'])
        df_s['Var'] = df_s.groupby('Nome do data point')['Valor'].diff().abs()
        df_v = df_s.groupby('Nome do data point')['Var'].sum().reset_index()
        fig_vol = px.bar(df_v.sort_values('Var', ascending=False), x='Nome do data point', y='Var',
                        title="Volatilidade Mensal Acumulada", color_discrete_sequence=['orange'])
        fig_vol.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_v['Nome do data point'].unique()))
        st.plotly_chart(fig_vol, use_container_width=True)

    st.divider()
    st.subheader("🗓️ Heatmap Mensal")
    df_pivot = df_mes.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean')
    fig_hm = px.imshow(df_pivot, aspect="auto", color_continuous_scale="Viridis")
    fig_hm.update_yaxes(type='category', categoryorder='array', categoryarray=sorted(df_pivot.index.unique(), reverse=True))
    st.plotly_chart(fig_hm, use_container_width=True)

# --- FUNÇÕES DIÁRIAS ---
def renderizar_aba_curvas(df):
    # Diagnóstico primeiro
    st.subheader("🔍 Diagnóstico de Subperformance")
    margem = st.slider("Tolerância de Subperformance (%):", 5, 50, 10)
    df_p = df[(df['Tempo'].dt.hour >= 6) & (df['Tempo'].dt.hour <= 18)]
    m_g = df_p['Valor'].mean()
    strings_abaixo = sorted([s for s in df_p['Nome do data point'].unique() if df_p[df_p['Nome do data point']==s]['Valor'].mean() < (m_g * (100-margem)/100)])
    sel = st.multiselect("Strings detectadas:", strings_abaixo, default=strings_abaixo)
    
    df_media = df.groupby('Tempo')['Valor'].mean().reset_index()
    fig_d = go.Figure()
    fig_d.add_trace(go.Scatter(x=df_media['Tempo'], y=df_media['Valor'], name="MÉDIA GLOBAL", line=dict(color='black', width=3, dash='dash')))
    for s in sel:
        fig_d.add_trace(go.Scatter(x=df[df['Nome do data point']==s]['Tempo'], y=df[df['Nome do data point']==s]['Valor'], name=s))
    fig_d.update_layout(plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_d, use_container_width=True)

    st.divider()

    # Panorama depois
    st.subheader("📈 Panorama Geral")
    fig_geral = px.line(df, x='Tempo', y='Valor', color='Nome do data point', title="Curvas de Corrente de Todas as Strings")
    fig_geral.update_layout(plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_geral, use_container_width=True)

# --- MAIN ---
st.sidebar.header("📁 Gestão de Dados")
arquivo = st.sidebar.file_uploader("Carregar histórico:", type=["xlsx", "csv"])

if arquivo:
    df_full = carregar_dados(arquivo)
    if df_full is not None:
        meses = sorted(df_full['MesAno'].unique(), reverse=True)
        m_sel = st.sidebar.selectbox("Selecionar Mês:", meses)
        df_m = df_full[df_full['MesAno'] == m_sel]
        
        datas = sorted(df_m['Data Apenas'].unique(), reverse=True)
        d_sel = st.sidebar.selectbox("Selecionar Dia:", datas)
        df_d = df_m[df_m['Data Apenas'] == d_sel]
        
        st.sidebar.divider()
        str_list = sorted(df_full['Nome do data point'].unique())
        sel_str = st.sidebar.multiselect("Filtro de Strings:", str_list, default=str_list)
        
        if sel_str:
            df_fd = df_d[df_d['Nome do data point'].isin(sel_str)]
            df_fm = df_m[df_m['Nome do data point'].isin(sel_str)]
            
            t = st.tabs(["📊 Mensal", "📈 Curvas", "📦 Boxplot", "📊 Acumulado", "🗓️ Heatmap", "☀️ Atividade", "⚡ Estabilidade"])
            with t[0]: renderizar_aba_mensal(df_fm)
            with t[1]: renderizar_aba_curvas(df_fd)
            with t[2]: 
                f_box = px.box(df_fd, x='Nome do data point', y='Valor', color='Nome do data point', title="Dispersão Diária")
                f_box.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_fd['Nome do data point'].unique()))
                st.plotly_chart(f_box, use_container_width=True)
            with t[3]: 
                f_bar = px.bar(df_fd.groupby('Nome do data point')['Valor'].sum().reset_index(), x='Nome do data point', y='Valor', color='Nome do data point', title="Acumulado Diário")
                f_bar.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_fd['Nome do data point'].unique()))
                st.plotly_chart(f_bar, use_container_width=True)
            with t[4]: 
                f_heat = px.imshow(df_fd.pivot_table(index='Nome do data point', columns='Hora', values='Valor', aggfunc='mean'), aspect="auto", color_continuous_scale="Viridis", title="Heatmap Diário")
                f_heat.update_yaxes(type='category', categoryorder='array', categoryarray=sorted(df_fd['Nome do data point'].unique(), reverse=True))
                st.plotly_chart(f_heat, use_container_width=True)
            with t[5]: 
                df_a = df_fd[df_fd['Valor'] >= 0.5]
                if not df_a.empty:
                    res = df_a.groupby('Nome do data point').agg(Inicio=('Tempo', 'min'), Fim=('Tempo', 'max')).reset_index()
                    f_time = px.timeline(res, x_start="Inicio", x_end="Fim", y="Nome do data point", color="Nome do data point", title="Período Ativo")
                    f_time.update_yaxes(type='category', categoryorder='array', categoryarray=sorted(df_a['Nome do data point'].unique(), reverse=True))
                    st.plotly_chart(f_time, use_container_width=True)
            with t[6]:
                df_sv = df_fd.sort_values(['Nome do data point', 'Tempo'])
                df_sv['V'] = df_sv.groupby('Nome do data point')['Valor'].diff().abs()
                df_vol = df_sv.groupby('Nome do data point')['V'].sum().reset_index()
                f_v = px.bar(df_vol, x='Nome do data point', y='V', color='Nome do data point', title="Volatilidade Diária")
                f_v.add_hline(y=df_vol['V'].mean(), line_dash="dash", line_color="black")
                f_v.update_xaxes(type='category', categoryorder='array', categoryarray=sorted(df_fd['Nome do data point'].unique()))
                st.plotly_chart(f_v, use_container_width=True)
