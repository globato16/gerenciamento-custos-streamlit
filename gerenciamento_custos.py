import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Nome do arquivo para persistência dos dados
DATA_FILE = "dados_custos.csv" # Usado para testes locais
# SHEET_NAME = "Gerenciamento de Custos" # Nome da sua planilha no Google Sheets
# WORKSHEET_NAME = "Transacoes" # Nome da aba na planilha

# --- Funções de Gerenciamento de Categorias ---
CATEGORIES_ENTRADA_FILE = "categorias_entrada.txt"
CATEGORIES_GASTO_FILE = "categorias_gasto.txt"

def load_categories_from_file(file_path, default_categories):
    try:
        with open(file_path, 'r') as f:
            categories = [line.strip() for line in f if line.strip()]
            return categories if categories else default_categories
    except FileNotFoundError:
        return default_categories

def save_categories_to_file(file_path, categories_list):
    with open(file_path, 'w') as f:
        for category in categories_list:
            f.write(f"{category}\n")

# Carregar categorias separadas
CATEGORIAS_ENTRADA = load_categories_from_file(CATEGORIES_ENTRADA_FILE, ["Salário", "Outras Entradas"])
CATEGORIAS_GASTO = load_categories_from_file(CATEGORIES_GASTO_FILE, ["Aluguel", "Alimentação", "Combustível", "Água", "Luz", "Gás", "Condomínio", "Lazer", "Investimentos", "Outros Gastos"])
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

# Função para carregar os dados
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
    return df

# --- Interface Streamlit ---
st.set_page_config(layout="wide", page_title="Gerenciamento de Custos Pessoais")

# --- Autenticação Básica ---
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
    def main():
        st.title("💰 Gerenciamento de Custos Pessoais")

        # Carregar perfis
        profiles = load_profiles()

        # Abas
        tab_titles = ["Análise Geral"] + profiles + ["Gerenciamento de Perfis", "Gerenciamento de Categorias"]
        tabs = st.tabs(tab_titles)

        # Aba de Análise Geral
        with tabs[0]:
            general_analysis_tab(profiles)

        # Abas de Perfil
        for i, profile in enumerate(profiles):
            with tabs[i + 1]:
                profile_tab(profile)

        # Aba de Gerenciamento de Perfis
        with tabs[-2]:
            manage_profiles_tab()
            
        # Aba de Gerenciamento de Categorias
        with tabs[-1]:
            manage_categories_tab()

    def general_analysis_tab(profiles):
        st.header("Análise Geral de Todos os Perfis")
        
        all_data = []
        for profile in profiles:
            df_profile = load_data(profile)
            if not df_profile.empty:
                df_profile["Pessoa"] = profile
                all_data.append(df_profile)
                
        if not all_data:
            st.info("Nenhuma transação cadastrada em nenhum perfil.")
            return

        df_all = pd.concat(all_data, ignore_index=True)
        
        st.subheader("Tabela de Transações (Edição e Exclusão)")
        
        edited_df = st.data_editor(
            df_all,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            }
        )
        
        if not edited_df.equals(df_all):
            # A exclusão de linhas é tratada automaticamente pelo st.data_editor.
            # O que precisamos fazer é garantir que o DataFrame final para cada perfil
            # seja salvo, tratando tanto edições quanto exclusões.
            
            # 1. Identificar as transações que permanecem para cada perfil
            for profile in profiles:
                # Filtra o DataFrame editado para pegar apenas as linhas que pertencem ao perfil atual
                df_profile_updated = edited_df[edited_df["Pessoa"] == profile].drop(columns=["Pessoa"])
                
                # Salva o DataFrame atualizado (que pode ter menos linhas se houve exclusão)
                save_data(df_profile_updated, profile)
                
            st.success("Transações atualizadas com sucesso (edições e exclusões salvas)!")
            st.rerun()

    def profile_tab(profile):
        st.header(f"Perfil: {profile}")
        
        df_profile = load_data(profile)
        
        with st.sidebar.form(f"add_transaction_form_{profile}"):
            st.header(f"Adicionar Transação ({profile})")
            data = st.date_input("Data")
            tipo = st.selectbox("Tipo", ["Entrada", "Gasto"])
            
            categorias_filtradas = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO
            categoria = st.selectbox("Categoria", categorias_filtradas)
                
            descricao = st.text_input("Descrição")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
            submitted = st.form_submit_button("Adicionar")
            
            if submitted:
                df_profile = add_transaction(df_profile, data, tipo, categoria, descricao, valor, profile)
                st.success("Transação adicionada com sucesso!")
                st.rerun()
        
        st.header("Tabela de Transações")
        
        edited_df = st.data_editor(
            df_profile,
            key=f"data_editor_{profile}", # Adicionando chave única
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            }
        )
        
        # Lógica de salvamento para edição e exclusão na aba de perfil
        if not edited_df.equals(df_profile):
            # O st.data_editor já trata a exclusão. Basta salvar o DataFrame resultante.
            save_data(edited_df, profile)
            st.success("Transações atualizadas com sucesso (edições e exclusões salvas)!")
            st.rerun()

    def manage_profiles_tab():
        st.header("Gerenciamento de Perfis")
        
        profiles = load_profiles()
        
        st.subheader("Perfis Atuais")
        st.write(", ".join(profiles))
        
        with st.form("add_profile_form"):
            new_profile = st.text_input("Novo Perfil (Ex: 'Filho 1', 'Casa')").strip()
            submitted = st.form_submit_button("Adicionar Perfil")
            
            if submitted and new_profile:
                if new_profile not in profiles:
                    profiles.append(new_profile)
                    save_profiles(profiles)
                    st.success(f"Perfil '{new_profile}' adicionado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Este perfil já existe.")

        st.subheader("Remover Perfil")
        profile_to_remove = st.selectbox("Selecione o Perfil para Remover", profiles)
        
        if st.button("Remover Perfil"):
            if profile_to_remove:
                profiles.remove(profile_to_remove)
                save_profiles(profiles)
                st.success(f"Perfil '{profile_to_remove}' removido com sucesso!")
                st.rerun()
            else:
                st.warning("Selecione um perfil para remover.")

    def manage_categories_tab():
        st.header("Gerenciamento de Categorias")
        
        global CATEGORIAS_ENTRADA, CATEGORIAS_GASTO
        
        st.subheader("Categorias de Entrada")
        st.write(", ".join(CATEGORIAS_ENTRADA))
        
        with st.form("add_entrada_form"):
            new_entrada = st.text_input("Nova Categoria de Entrada").strip()
            submitted_entrada = st.form_submit_button("Adicionar Entrada")
            
            if submitted_entrada and new_entrada:
                if new_entrada not in CATEGORIAS_ENTRADA:
                    CATEGORIAS_ENTRADA.append(new_entrada)
                    save_categories_to_file(CATEGORIES_ENTRADA_FILE, CATEGORIAS_ENTRADA)
                    st.success(f"Categoria de Entrada '{new_entrada}' adicionada.")
                    st.rerun()
                else:
                    st.warning("Esta categoria de Entrada já existe.")

        st.subheader("Remover Categoria de Entrada")
        entrada_to_remove = st.selectbox("Selecione para Remover (Entrada)", CATEGORIAS_ENTRADA)
        
        if st.button("Remover Entrada", key="remove_entrada"):
            if entrada_to_remove:
                CATEGORIAS_ENTRADA.remove(entrada_to_remove)
                save_categories_to_file(CATEGORIES_ENTRADA_FILE, CATEGORIAS_ENTRADA)
                st.success(f"Categoria de Entrada '{entrada_to_remove}' removida.")
                st.rerun()
                
        st.markdown("---")
        
        st.subheader("Categorias de Gasto")
        st.write(", ".join(CATEGORIAS_GASTO))
        
        with st.form("add_gasto_form"):
            new_gasto = st.text_input("Nova Categoria de Gasto").strip()
            submitted_gasto = st.form_submit_button("Adicionar Gasto")
            
            if submitted_gasto and new_gasto:
                if new_gasto not in CATEGORIAS_GASTO:
                    CATEGORIAS_GASTO.append(new_gasto)
                    save_categories_to_file(CATEGORIES_GASTO_FILE, CATEGORIAS_GASTO)
                    st.success(f"Categoria de Gasto '{new_gasto}' adicionada.")
                    st.rerun()
                else:
                    st.warning("Esta categoria de Gasto já existe.")

        st.subheader("Remover Categoria de Gasto")
        gasto_to_remove = st.selectbox("Selecione para Remover (Gasto)", CATEGORIAS_GASTO)
        
        if st.button("Remover Gasto", key="remove_gasto"):
            if gasto_to_remove:
                CATEGORIAS_GASTO.remove(gasto_to_remove)
                save_categories_to_file(CATEGORIES_GASTO_FILE, CATEGORIAS_GASTO)
                st.success(f"Categoria de Gasto '{gasto_to_remove}' removida.")
                st.rerun()

    if __name__ == "__main__":
        main()
