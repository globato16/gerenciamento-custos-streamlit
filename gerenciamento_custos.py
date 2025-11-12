import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Nome do arquivo para persistência dos dados
DATA_FILE = "dados_custos.csv" # Usado para testes locais
# SHEET_NAME = "Gerenciamento de Custos" # Nome da sua planilha no Google Sheets
# WORKSHEET_NAME = "Transacoes" # Nome da aba na planilha

# Categorias
CATEGORIAS_ENTRADA = ['Salário', 'Outras Entradas']
CATEGORIAS_GASTO = ['Aluguel', 'Alimentação', 'Combustível', 'Água', 'Luz', 'Gás', 'Condomínio', 'Lazer', 'Investimentos', 'Outros Gastos']
TODAS_CATEGORIAS = CATEGORIAS_ENTRADA + CATEGORIAS_GASTO

# Metas de Gastos (Exemplo: Valores mensais em R$)
METAS_GASTOS = {
    'Aluguel': 1500.00,
    'Alimentação': 1000.00,
    'Combustível': 400.00,
    'Água': 100.00,
    'Luz': 150.00,
    'Gás': 50.00,
    'Condomínio': 300.00,
    'Lazer': 500.00,
    'Investimentos': 500.00,
    'Outros Gastos': 200.00
}

# --- Funções de Gerenciamento de Perfis ---
PROFILES_FILE = "perfis.txt"

def load_profiles():
    try:
        with open(PROFILES_FILE, 'r') as f:
            profiles = [line.strip() for line in f if line.strip()]
            if not profiles:
                return ['Principal']
            return profiles
    except FileNotFoundError:
        return ['Principal']

def save_profiles(profiles_list):
    with open(PROFILES_FILE, 'w') as f:
        for profile in profiles_list:
            f.write(f"{profile}\n")

# Metas de Gastos (Exemplo: Valores mensais em R$)
METAS_GASTOS = {
    'Aluguel': 1500.00,
    'Alimentação': 1000.00,
    'Combustível': 400.00,
    'Água': 100.00,
    'Luz': 150.00,
    'Gás': 50.00,
    'Condomínio': 300.00,
    'Lazer': 500.00,
    'Investimentos': 500.00,
    'Outros Gastos': 200.00
}

# Função para inicializar a conexão com o Google Sheets
# @st.cache_resource
# def get_gsheet_client():
#     import gspread
#     # Autenticação usando o segredo do Streamlit (para implantação)
#     # Em ambiente local, você pode usar gspread.service_account()
#     try:
#         gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
#     except Exception as e:
#         st.error(f"Erro de autenticação com Google Sheets. Verifique o arquivo secrets.toml. Erro: {e}")
#         st.stop()
#     return gc

# Função para carregar os dad# Função para carregar os dados
def load_data(profile):
    try:
        df = pd.read_csv(f"{profile}_{DATA_FILE}")
        df['Data'] = pd.to_datetime(df['Data'])
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor'])

# Função para salvar os dados
def save_data(df, profile):
    df.to_csv(f"{profile}_{DATA_FILE}", index=False)
# Função para adicionar uma nova transação
def add_transaction(df, data, tipo, categoria, descricao, valor, profile):
    new_transaction = pd.DataFrame([{
        'Data': pd.to_datetime(data),
        'Tipo': tipo,
        'Categoria': categoria,
        'Descrição': descricao,
        'Valor': float(valor)
    }])
    df = pd.concat([df, new_transaction], ignore_index=True)
    save_data(df, profile)
    return df# --- Interface Streamlit ---

st.set_page_config(layout="wide", page_title="Gerenciamento de Custos Pessoais")

# --- Autenticação Básica ---
# Credenciais fixas para demonstração. Mude-as para produção!
USERNAME = "familia"
PASSWORD = "cabuloso"

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("Login - Gerenciamento de Custos Pessoais")
    
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        
        if submitted:
            if username == USERNAME and password == PASSWORD:
                st.session_state['logged_in'] = True
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    
else:
    # Conteúdo principal do aplicativo
    st.title("💰 Gerenciamento de Custos Pessoais")

    # Carregar lista de perfis
    profiles = load_profiles()
    
    # --- Abas de Navegação ---
    tab_titles = ["Análise Geral"] + profiles + ["Gerenciamento de Perfis"]
    tabs = st.tabs(tab_titles)
    
    # --- Aba de Análise Geral ---
    with tabs[0]:
        st.header("Análise Geral de Todos os Perfis")
        
        # Carregar todos os dados de todos os perfis para a análise geral
        all_data = []
        for profile in profiles:
            df_profile = load_data(profile)
            all_data.append(df_profile)
            
        if all_data:
            df = pd.concat(all_data, ignore_index=True)
        else:
            df = pd.DataFrame(columns=['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'Pessoa'])
            
        # --- Configuração de Metas (Apenas para visualização) ---
        st.sidebar.header("Configuração de Metas")

        # Nova Meta de Gastos Total Mensal
        META_GASTO_TOTAL = st.sidebar.number_input("Meta de Gasto Total Mensal (R$)", value=4000.00, min_value=0.0, step=100.0, key="meta_gasto_total_geral")

        # Metas por Categoria
        for categoria, meta in METAS_GASTOS.items():
            METAS_GASTOS[categoria] = st.sidebar.number_input(f"Meta de {categoria} (R$)", value=meta, min_value=0.0, step=10.0, key=f"meta_{categoria}_geral")

        # --- Visualização de Dados ---
        if not df.empty:
            # 1. Tabela de Dados Interativa
            st.header("Tabela de Transações (Apenas Visualização)")
            
            # Ordenar por data para exibição
            df_sorted = df.sort_values(by='Data', ascending=False).reset_index(drop=True)
            
            st.dataframe(df_sorted, use_container_width=True)
            
            # --- Resumo Mensal ---
            st.header("Resumo Mensal")
            
            # Agrupar por Mês/Ano
            df_resumo = df.copy()
            df_resumo['Mes_Ano'] = df_resumo['Data'].dt.to_period('M').astype(str)
            
            # Calcular Entradas e Gastos
            entradas = df_resumo[df_resumo['Tipo'] == 'Entrada'].groupby('Mes_Ano')['Valor'].sum().reset_index()
            gastos = df_resumo[df_resumo['Tipo'] == 'Gasto'].groupby('Mes_Ano')['Valor'].sum().reset_index()
            
            # Renomear colunas
            entradas.rename(columns={'Valor': 'Entradas'}, inplace=True)
            gastos.rename(columns={'Valor': 'Gastos'}, inplace=True)
            
            # Juntar e calcular o Saldo
            resumo_mensal = pd.merge(entradas, gastos, on='Mes_Ano', how='outer').fillna(0)
            resumo_mensal['Saldo'] = resumo_mensal['Entradas'] - resumo_mensal['Gastos']
            
            # Ordenar
            resumo_mensal.sort_values(by='Mes_Ano', inplace=True, ascending=False)
            
            # Exibir o mês mais recente
            mes_recente = resumo_mensal.iloc[0]
            
            col1, col2, col3 = st.columns(3)
            
            # Sobra Mensal (Saldo)
            sobra_mensal = mes_recente['Saldo']
            if sobra_mensal >= 0:
                col1.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Superávit", delta_color="normal")
            else:
                col1.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Déficit", delta_color="inverse")
                
            # Meta de Gasto Total
            gastos_mes = mes_recente['Gastos']
            meta_gasto_total = META_GASTO_TOTAL
            diferenca_meta = meta_gasto_total - gastos_mes
            
            if diferenca_meta >= 0:
                delta_meta = f"R$ {diferenca_meta:,.2f} Abaixo da Meta".replace(",", "X").replace(".", ",").replace("X", ".")
                delta_color = "normal"
            else:
                delta_meta = f"R$ {-diferenca_meta:,.2f} Acima da Meta".replace(",", "X").replace(".", ",").replace("X", ".")
                delta_color = "inverse"
                
            col2.metric("Meta de Gasto Total", f"R$ {gastos_mes:,.2f} / R$ {meta_gasto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=delta_meta, delta_color=delta_color)
            
            # Progresso da Meta
            progresso = min(gastos_mes / meta_gasto_total, 1.0) if meta_gasto_total > 0 else 0
            col3.markdown(f"**Progresso da Meta: {progresso * 100:.2f}%**")
            col3.progress(progresso)
            
            # --- Gráfico de Evolução Mensal ---
            st.header("Evolução Mensal (Entradas, Gastos e Saldo)")
            
            # Reordenar para o gráfico
            resumo_mensal_plot = resumo_mensal.sort_values(by='Mes_Ano', ascending=True)
            
            fig_evolucao = px.line(
                resumo_mensal_plot,
                x='Mes_Ano',
                y=['Entradas', 'Gastos', 'Saldo'],
                title='Evolução Mensal',
                labels={'Mes_Ano': 'Mês/Ano', 'value': 'Valor (R$)', 'variable': 'Tipo'},
                height=400
            )
            fig_evolucao.update_layout(hovermode="x unified")
            st.plotly_chart(fig_evolucao, use_container_width=True)
            
            # --- Gráfico de Percentual de Gastos ---
            st.header("Percentual de Gastos por Categoria")
            
            # Filtrar o mês mais recente para o gráfico de pizza
            df_gastos_mes = df_resumo[(df_resumo['Tipo'] == 'Gasto') & (df_resumo['Mes_Ano'] == mes_recente['Mes_Ano'])]
            
            if not df_gastos_mes.empty:
                gastos_por_categoria = df_gastos_mes.groupby('Categoria')['Valor'].sum().reset_index()
                
                # Calcular o progresso da meta por categoria
                gastos_por_categoria['Meta'] = gastos_por_categoria['Categoria'].apply(lambda x: METAS_GASTOS.get(x, 0))
                gastos_por_categoria['Progresso'] = gastos_por_categoria.apply(lambda row: min(row['Valor'] / row['Meta'], 1.0) if row['Meta'] > 0 else 0, axis=1)
                
                # Tabela de Progresso da Meta
                st.subheader(f"Progresso da Meta por Categoria - {mes_recente['Mes_Ano']}")
                st.dataframe(
                    gastos_por_categoria.style.format({
                        'Valor': "R$ {:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Meta': "R$ {:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Progresso': "{:.2%}"
                    }),
                    use_container_width=True
                )
                
                # Gráfico de Pizza
                fig_pizza = px.pie(
                    gastos_por_categoria,
                    values='Valor',
                    names='Categoria',
                    title=f'Distribuição de Gastos - {mes_recente["Mes_Ano"]}',
                    hole=.3
                )
                st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.info(f"Nenhum gasto registrado no mês de {mes_recente['Mes_Ano']}.")
                
        else:
            st.info("Nenhuma transação registrada ainda. Use as abas de perfil para adicionar sua primeira transação.")

    # --- Abas de Perfil ---
    for i, profile in enumerate(profiles):
        with tabs[i + 1]:
            st.header(f"Transações e Análise de {profile}")
            
            # Carregar dados do perfil
            df_profile = load_data(profile)
            
            # --- Sidebar para Adicionar Transação ---
            with st.sidebar:
                st.header(f"Adicionar Transação para {profile}")
                
                with st.form(f"add_transaction_form_{profile}"):
                    data = st.date_input("Data", value="today", key=f"data_{profile}")
                    tipo = st.radio("Tipo", ['Entrada', 'Gasto'], key=f"tipo_{profile}")
                    
                    if tipo == 'Entrada':
                        categoria_options = CATEGORIAS_ENTRADA
                    else:
                        categoria_options = CATEGORIAS_GASTO
                        
                    categoria = st.selectbox("Categoria", categoria_options, key=f"categoria_{profile}")
                    pessoa = profile # A pessoa é o nome da aba
                    descricao = st.text_input("Descrição", key=f"descricao_{profile}")
                    valor = st.number_input("Valor", min_value=0.01, step=0.01, key=f"valor_{profile}")
                    
                    submitted = st.form_submit_button("Adicionar Transação")
                    
                    if submitted:
                        df_profile = add_transaction(df_profile, data, tipo, categoria, descricao, valor, pessoa)
                        st.success("Transação adicionada com sucesso!")
                        st.rerun()
                        
            # --- Visualização de Dados do Perfil ---
            if not df_profile.empty:
                # 1. Tabela de Dados Interativa
                st.subheader("Tabela de Transações (Edição e Exclusão)")
                
                # Ordenar por data para exibição
                df_sorted_profile = df_profile.sort_values(by='Data', ascending=False).reset_index(drop=True)
                
                # Usar st.data_editor para permitir edição e exclusão
                edited_df_profile = st.data_editor(
                    df_sorted_profile,
                    use_container_width=True,
                    num_rows="dynamic", # Permite adicionar e excluir linhas
                    hide_index=True,
                    column_config={
                        "Data": st.column_config.DateColumn("Data", format="YYYY-MM-DD", required=True),
                        "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto'], required=True),
                        "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS, required=True),
                        "Pessoa": st.column_config.TextColumn("Pessoa", disabled=True), # Desabilitado, pois é o nome do perfil
                        "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                        "Descrição": st.column_config.TextColumn("Descrição"),
                    }
                )
                
                # Lógica para salvar as alterações do data_editor
                if not edited_df_profile.equals(df_sorted_profile):
                    # Vamos filtrar as linhas vazias que podem ter sido adicionadas e não preenchidas.
                    edited_df_clean_profile = edited_df_profile.dropna(subset=['Data', 'Tipo', 'Categoria', 'Valor'])
                    
                    # Se o número de linhas mudou, ou se houve edição, salvamos.
                    if len(edited_df_clean_profile) != len(df_profile) or not edited_df_clean_profile.equals(df_profile):
                        # A coluna 'Pessoa' não é mais necessária, pois o nome da aba já a define.
                        # O save_data já espera o nome do perfil.
                        save_data(edited_df_clean_profile, profile)
                        st.success("Transações atualizadas com sucesso! (Edição/Exclusão)")
                        st.rerun()
                        
                # --- Resumo Mensal ---
                st.subheader("Resumo Mensal")
                
                # Agrupar por Mês/Ano
                df_resumo_profile = df_profile.copy()
                df_resumo_profile['Mes_Ano'] = df_resumo_profile['Data'].dt.to_period('M').astype(str)
                
                # Calcular Entradas e Gastos
                entradas_profile = df_resumo_profile[df_resumo_profile['Tipo'] == 'Entrada'].groupby('Mes_Ano')['Valor'].sum().reset_index()
                gastos_profile = df_resumo_profile[df_resumo_profile['Tipo'] == 'Gasto'].groupby('Mes_Ano')['Valor'].sum().reset_index()
                
                # Renomear colunas
                entradas_profile.rename(columns={'Valor': 'Entradas'}, inplace=True)
                gastos_profile.rename(columns={'Valor': 'Gastos'}, inplace=True)
                
                # Juntar e calcular o Saldo
                resumo_mensal_profile = pd.merge(entradas_profile, gastos_profile, on='Mes_Ano', how='outer').fillna(0)
                resumo_mensal_profile['Saldo'] = resumo_mensal_profile['Entradas'] - resumo_mensal_profile['Gastos']
                
                # Ordenar
                resumo_mensal_profile.sort_values(by='Mes_Ano', inplace=True, ascending=False)
                
                # Exibir o mês mais recente
                mes_recente_profile = resumo_mensal_profile.iloc[0]
                
                col1_p, col2_p, col3_p = st.columns(3)
                
                # Sobra Mensal (Saldo)
                sobra_mensal_profile = mes_recente_profile['Saldo']
                if sobra_mensal_profile >= 0:
                    col1_p.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal_profile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Superávit", delta_color="normal")
                else:
                    col1_p.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal_profile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Déficit", delta_color="inverse")
                    
                # Meta de Gasto Total
                gastos_mes_profile = mes_recente_profile['Gastos']
                meta_gasto_total_profile = META_GASTO_TOTAL # Usando a meta geral por enquanto
                diferenca_meta_profile = meta_gasto_total_profile - gastos_mes_profile
                
                if diferenca_meta_profile >= 0:
                    delta_meta_profile = f"R$ {diferenca_meta_profile:,.2f} Abaixo da Meta".replace(",", "X").replace(".", ",").replace("X", ".")
                    delta_color_profile = "normal"
                else:
                    delta_meta_profile = f"R$ {-diferenca_meta_profile:,.2f} Acima da Meta".replace(",", "X").replace(".", ",").replace("X", ".")
                    delta_color_profile = "inverse"
                    
                col2_p.metric("Meta de Gasto Total", f"R$ {gastos_mes_profile:,.2f} / R$ {meta_gasto_total_profile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=delta_meta_profile, delta_color=delta_color_profile)
                
                # Progresso da Meta
                progresso_profile = min(gastos_mes_profile / meta_gasto_total_profile, 1.0) if meta_gasto_total_profile > 0 else 0
                col3_p.markdown(f"**Progresso da Meta: {progresso_profile * 100:.2f}%**")
                col3_p.progress(progresso_profile)
                
                # --- Gráfico de Evolução Mensal ---
                st.subheader("Evolução Mensal (Entradas, Gastos e Saldo)")
                
                # Reordenar para o gráfico
                resumo_mensal_plot_profile = resumo_mensal_profile.sort_values(by='Mes_Ano', ascending=True)
                
                fig_evolucao_profile = px.line(
                    resumo_mensal_plot_profile,
                    x='Mes_Ano',
                    y=['Entradas', 'Gastos', 'Saldo'],
                    title=f'Evolução Mensal - {profile}',
                    labels={'Mes_Ano': 'Mês/Ano', 'value': 'Valor (R$)', 'variable': 'Tipo'},
                    height=400
                )
                fig_evolucao_profile.update_layout(hovermode="x unified")
                st.plotly_chart(fig_evolucao_profile, use_container_width=True)
                
                # --- Gráfico de Percentual de Gastos ---
                st.subheader("Percentual de Gastos por Categoria")
                
                # Filtrar o mês mais recente para o gráfico de pizza
                df_gastos_mes_profile = df_resumo_profile[(df_resumo_profile['Tipo'] == 'Gasto') & (df_resumo_profile['Mes_Ano'] == mes_recente_profile['Mes_Ano'])]
                
                if not df_gastos_mes_profile.empty:
                    gastos_por_categoria_profile = df_gastos_mes_profile.groupby('Categoria')['Valor'].sum().reset_index()
                    
                    # Calcular o progresso da meta por categoria
                    gastos_por_categoria_profile['Meta'] = gastos_por_categoria_profile['Categoria'].apply(lambda x: METAS_GASTOS.get(x, 0))
                    gastos_por_categoria_profile['Progresso'] = gastos_por_categoria_profile.apply(lambda row: min(row['Valor'] / row['Meta'], 1.0) if row['Meta'] > 0 else 0, axis=1)
                    
                    # Tabela de Progresso da Meta
                    st.caption(f"Progresso da Meta por Categoria - {mes_recente_profile['Mes_Ano']}")
                    st.dataframe(
                        gastos_por_categoria_profile.style.format({
                            'Valor': "R$ {:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                            'Meta': "R$ {:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                            'Progresso': "{:.2%}"
                        }),
                        use_container_width=True
                    )
                    
                    # Gráfico de Pizza
                    fig_pizza_profile = px.pie(
                        gastos_por_categoria_profile,
                        values='Valor',
                        names='Categoria',
                        title=f'Distribuição de Gastos - {profile} - {mes_recente_profile["Mes_Ano"]}',
                        hole=.3
                    )
                    st.plotly_chart(fig_pizza_profile, use_container_width=True)
                else:
                    st.info(f"Nenhum gasto registrado no mês de {mes_recente_profile['Mes_Ano']} para {profile}.")
                    
            else:
                st.info(f"Nenhuma transação registrada para o perfil {profile}.")

    # --- Aba de Cadastro de Perfis ---
    with tabs[len(profiles) + 1]:
        st.header("Gerenciamento de Perfis")
        
        st.subheader("Perfis Cadastrados")
        df_profiles = pd.DataFrame({'Perfil': profiles})
        edited_profiles = st.data_editor(
            df_profiles,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={"Perfil": st.column_config.TextColumn("Nome do Perfil", required=True)}
        )
        
        if not edited_profiles.equals(df_profiles):
            new_profiles = edited_profiles['Perfil'].dropna().unique().tolist()
            save_profiles(new_profiles)
            st.success("Perfis atualizados com sucesso! Recarregando...")
            st.rerun()


    st.header("Resumo Mensal")
    
    # Agrupar por Mês/Ano
    df_resumo = df.copy()
    df_resumo['AnoMês'] = df_resumo['Data'].dt.to_period('M').astype(str)
    
    # Calcular Entradas e Gastos por mês
    resumo_mensal = df_resumo.groupby(['AnoMês', 'Tipo'])['Valor'].sum().unstack(fill_value=0)
    
    if 'Entrada' not in resumo_mensal.columns:
        resumo_mensal['Entrada'] = 0
    if 'Gasto' not in resumo_mensal.columns:
        resumo_mensal['Gasto'] = 0
        
    resumo_mensal['Saldo'] = resumo_mensal['Entrada'] - resumo_mensal['Gasto']
    resumo_mensal = resumo_mensal.reset_index()
    
    # --- Sobra Mensal e Avaliação da Meta ---
    st.subheader("Sobra Mensal e Avaliação da Meta")
    
    # Selecionar o mês mais recente para exibição do resumo
    mes_atual = resumo_mensal['AnoMês'].max()
    resumo_mes_atual = resumo_mensal[resumo_mensal['AnoMês'] == mes_atual].iloc[0]
    
    total_entrada = resumo_mes_atual['Entrada']
    total_gasto = resumo_mes_atual['Gasto']
    sobra_mensal = resumo_mes_atual['Saldo']
    
    col1, col2, col3 = st.columns(3)
    
    # Sobra Mensal
    if sobra_mensal >= 0:
        col1.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal:,.2f}", delta="Superávit", delta_color="normal")
    else:
        col1.metric("Sobra Mensal (Saldo)", f"R$ {sobra_mensal:,.2f}", delta="Déficit", delta_color="inverse")
        
    # Avaliação da Meta de Gasto Total
    meta_atingida = total_gasto / META_GASTO_TOTAL
    meta_diferenca = META_GASTO_TOTAL - total_gasto
    
    if meta_diferenca >= 0:
        col2.metric("Meta de Gasto Total", f"R$ {total_gasto:,.2f} / R$ {META_GASTO_TOTAL:,.2f}", delta=f"R$ {meta_diferenca:,.2f} abaixo da meta", delta_color="normal")
    else:
        col2.metric("Meta de Gasto Total", f"R$ {total_gasto:,.2f} / R$ {META_GASTO_TOTAL:,.2f}", delta=f"R$ {-meta_diferenca:,.2f} acima da meta", delta_color="inverse")
        
    col3.progress(min(meta_atingida, 1.0), text=f"Progresso da Meta: {meta_atingida*100:.2f}%")
    
    st.markdown("---")
    
    # Gráfico de Linha (Evolução Mês a Mês)
    st.subheader("Evolução de Entradas, Gastos e Saldo")
    
    fig_evolucao = px.line(
        resumo_mensal,
        x='AnoMês',
        y=['Entrada', 'Gasto', 'Saldo'],
        title='Evolução Mensal',
        labels={'value': 'Valor (R$)', 'variable': 'Tipo'},
        markers=True
    )
    fig_evolucao.update_layout(hovermode="x unified")
    st.plotly_chart(fig_evolucao, use_container_width=True)
    
    # 3. Análise de Gastos por Categoria (Percentual)
    st.header("Análise de Gastos")
    
    df_gastos = df[df['Tipo'] == 'Gasto']
    
    if not df_gastos.empty:
        
        # Filtro de Mês/Ano para a análise de gastos
        meses_disponiveis = sorted(df_resumo['AnoMês'].unique(), reverse=True)
        mes_selecionado = st.selectbox("Selecione o Mês para Análise de Gastos", meses_disponiveis)
        
        df_gastos_mes = df_gastos[df_gastos['Data'].dt.to_period('M').astype(str) == mes_selecionado]
        
        if not df_gastos_mes.empty:
            gastos_por_categoria = df_gastos_mes.groupby('Categoria')['Valor'].sum().reset_index()
            
            # Adicionar a meta de gastos
            gastos_por_categoria['Meta'] = gastos_por_categoria['Categoria'].map(METAS_GASTOS)
            gastos_por_categoria['Progresso'] = (gastos_por_categoria['Valor'] / gastos_por_categoria['Meta'])
            
            # Gráfico de Pizza (Percentual de Gastos)
            st.subheader(f"Percentual de Gastos por Categoria em {mes_selecionado}")
            
            fig_pizza = px.pie(
                gastos_por_categoria,
                values='Valor',
                names='Categoria',
                title=f'Distribuição de Gastos em {mes_selecionado}',
                hole=.3
            )
            fig_pizza.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pizza, use_container_width=True)
            
            # Tabela de Gastos por Categoria e Progresso da Meta
            st.subheader(f"Progresso da Meta de Gastos em {mes_selecionado}")
            
            # Criar uma tabela para visualização de progresso
            tabela_progresso = gastos_por_categoria.copy()
            tabela_progresso['Percentual'] = (tabela_progresso['Valor'] / tabela_progresso['Valor'].sum()) * 100
            tabela_progresso = tabela_progresso.sort_values(by='Valor', ascending=False)
            
            # Adicionar coluna de progresso visual
            tabela_progresso['Status da Meta'] = tabela_progresso.apply(
                lambda row: f"{row['Valor']:.2f} / {row['Meta']:.2f} ({(row['Progresso'] * 100):.2f}%)", axis=1
            )
            
            st.dataframe(
                tabela_progresso[['Categoria', 'Valor', 'Meta', 'Progresso', 'Status da Meta', 'Percentual']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor": st.column_config.NumberColumn("Total Gasto (R$)", format="R$ %.2f"),
                    "Meta": st.column_config.NumberColumn("Meta (R$)", format="R$ %.2f"),
                    "Percentual": st.column_config.NumberColumn("Percentual", format="%.2f %%"),
                    "Progresso": st.column_config.ProgressColumn(
                        "Progresso da Meta",
                        format="%.2f",
                        min_value=0,
                        max_value=1
                    ),
                    "Status da Meta": st.column_config.TextColumn("Status da Meta"),
                },
                column_order=("Categoria", "Valor", "Meta", "Progresso", "Status da Meta", "Percentual")
            )
        else:
            st.info(f"Nenhum gasto registrado em {mes_selecionado}.")
    else:
        st.info("Nenhum gasto registrado ainda.")



# --- Fim do Script ---
