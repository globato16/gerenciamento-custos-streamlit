import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Nome do arquivo para persistência dos dados
DATA_FILE = "dados_custos.csv"

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

# --- Funções de dados ---
def load_data(profile):
    try:
        df = pd.read_csv(f"{profile}_{DATA_FILE}")
        df['Data'] = pd.to_datetime(df['Data'])
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor'])

def save_data(df, profile):
    df.to_csv(f"{profile}_{DATA_FILE}", index=False)

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

# --- Configuração da Página ---
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
    # --- Funções de Gráficos ---
    import plotly.graph_objects as go

    def plot_trend_chart(df, title="Tendência de Gastos e Entradas"):
        if df.empty:
            st.info("Sem dados para exibir o gráfico de tendência.")
            return
        df['Ano-Mês'] = df['Data'].dt.to_period('M').astype(str)
        grouped = df.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().reset_index()
        fig = px.line(
            grouped,
            x='Ano-Mês',
            y='Valor',
            color='Tipo',
            markers=True,
            title=title
        )
        fig.update_layout(xaxis_title="Mês", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    def plot_category_chart(df, title="Distribuição por Categoria"):
        if df.empty:
            st.info("Sem dados para exibir a distribuição de categorias.")
            return
        grouped = df.groupby('Categoria')['Valor'].sum().reset_index().sort_values('Valor', ascending=False)
        fig = px.bar(
            grouped,
            x='Categoria',
            y='Valor',
            text_auto=True,
            title=title
        )
        fig.update_layout(xaxis_title="", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    def plot_profile_comparison(df_all):
        if df_all.empty:
            st.info("Sem dados para comparação de perfis.")
            return
        grouped = df_all.groupby(['Pessoa', 'Tipo'])['Valor'].sum().reset_index()
        fig = px.bar(
            grouped,
            x='Pessoa',
            y='Valor',
            color='Tipo',
            barmode='group',
            title="Comparativo de Entradas e Gastos por Perfil"
        )
        fig.update_layout(template="plotly_white", yaxis_title="Valor (R$)")
        st.plotly_chart(fig, use_container_width=True)

    # --- Interface Principal ---
    def main():
        st.title("💰 Gerenciamento de Custos Pessoais")

        profiles = load_profiles()
        tab_titles = ["Análise Geral"] + profiles + ["Gerenciamento de Perfis", "Gerenciamento de Categorias"]
        tabs = st.tabs(tab_titles)

        with tabs[0]:
            general_analysis_tab(profiles)

        for i, profile in enumerate(profiles):
            with tabs[i + 1]:
                profile_tab(profile)

        with tabs[-2]:
            manage_profiles_tab()

        with tabs[-1]:
            manage_categories_tab()

    # --- Análise Geral ---
    def general_analysis_tab(profiles):
        st.header("📊 Análise Geral de Todos os Perfis")

        all_data = []
        for profile in profiles:
            df_profile = load_data(profile)
            if not df_profile.empty:
                df_profile["Pessoa"] = profile
                all_data.append(df_profile)

        if not all_data:
            st.info("Nenhuma transação cadastrada.")
            return

        df_all = pd.concat(all_data, ignore_index=True)

        # --- Filtros ---
        st.sidebar.subheader("Filtros - Análise Geral")
        start_date = st.sidebar.date_input("Data Inicial", df_all['Data'].min())
        end_date = st.sidebar.date_input("Data Final", df_all['Data'].max())
        df_filtered = df_all[(df_all['Data'] >= pd.to_datetime(start_date)) & (df_all['Data'] <= pd.to_datetime(end_date))]

        st.write(f"Período selecionado: **{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}**")

        # --- Tabela primeiro ---
        st.subheader("🧾 Tabela de Transações (Edição e Exclusão)")

        edited_df = st.data_editor(
            df_filtered,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            }
        )

        if not edited_df.equals(df_filtered):
            for profile in profiles:
                df_profile_updated = edited_df[edited_df["Pessoa"] == profile].drop(columns=["Pessoa"])
                save_data(df_profile_updated, profile)
            st.success("Transações atualizadas com sucesso!")
            st.rerun()

        # --- Gráficos depois ---
        st.markdown("---")
        st.subheader("📈 Gráfico de Tendência")
        plot_trend_chart(df_filtered)

        st.subheader("🍕 Distribuição de Gastos por Categoria")
        plot_category_chart(df_filtered[df_filtered['Tipo'] == 'Gasto'])

        st.subheader("👥 Comparativo entre Perfis")
        plot_profile_comparison(df_filtered)

    # --- Aba de Perfil ---
    def profile_tab(profile):
        st.header(f"👤 Perfil: {profile}")

        df_profile = load_data(profile)

        st.sidebar.header(f"Adicionar Transação ({profile})")
        tipo = st.sidebar.selectbox("Tipo", ["Entrada", "Gasto"], key=f"tipo_select_{profile}")

        with st.sidebar.form(f"add_transaction_form_{profile}"):
            data = st.date_input("Data")
            categorias_filtradas = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO
            categoria = st.selectbox("Categoria", categorias_filtradas, key=f"categoria_select_{profile}")
            descricao = st.text_input("Descrição")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
            submitted = st.form_submit_button("Adicionar")
            if submitted:
                df_profile = add_transaction(df_profile, data, tipo, categoria, descricao, valor, profile)
                st.success("Transação adicionada com sucesso!")
                st.rerun()

        if df_profile.empty:
            st.info("Nenhuma transação neste perfil.")
            return

        # --- Filtros de data ---
        st.subheader("📅 Filtros de Análise")
        start_date = st.date_input("Data Inicial", df_profile['Data'].min(), key=f"start_{profile}")
        end_date = st.date_input("Data Final", df_profile['Data'].max(), key=f"end_{profile}")
        df_filtered = df_profile[(df_profile['Data'] >= pd.to_datetime(start_date)) & (df_profile['Data'] <= pd.to_datetime(end_date))]

        # --- Tabela primeiro ---
        st.subheader("🧾 Tabela de Transações")

        edited_df = st.data_editor(
            df_profile,
            key=f"data_editor_{profile}",
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            }
        )

        if not edited_df.equals(df_profile):
            save_data(edited_df, profile)
            st.success("Transações atualizadas com sucesso!")
            st.rerun()

        # --- Gráficos depois ---
        st.markdown("---")
        st.subheader("📈 Tendência de Gastos e Entradas")
        plot_trend_chart(df_filtered, title=f"Tendência - {profile}")

        st.subheader("🍕 Gastos por Categoria")
        plot_category_chart(df_filtered[df_filtered['Tipo'] == 'Gasto'], title=f"Distribuição de Gastos - {profile}")

        df_filtered['Ano-Mês'] = df_filtered['Data'].dt.to_period('M').astype(str)
        resumo = df_filtered.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().unstack(fill_value=0)
        resumo['Saldo'] = resumo.get('Entrada', 0) - resumo.get('Gasto', 0)

        st.subheader("📊 Resumo Mensal")
        st.dataframe(resumo)

    # --- Aba de Perfis ---
    def manage_profiles_tab():
        st.header("👥 Gerenciamento de Perfis")
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
            profiles.remove(profile_to_remove)
            save_profiles(profiles)
            st.success(f"Perfil '{profile_to_remove}' removido com sucesso!")
            st.rerun()

    # --- Aba de Categorias ---
    def manage_categories_tab():
        st.header("📂 Gerenciamento de Categorias")
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
                    st.success(f"Categoria '{new_entrada}' adicionada.")
                    st.rerun()

        st.subheader("Categorias de Gasto")
        st.write(", ".join(CATEGORIAS_GASTO))
        with st.form("add_gasto_form"):
            new_gasto = st.text_input("Nova Categoria de Gasto").strip()
            submitted_gasto = st.form_submit_button("Adicionar Gasto")
            if submitted_gasto and new_gasto:
                if new_gasto not in CATEGORIAS_GASTO:
                    CATEGORIAS_GASTO.append(new_gasto)
                    save_categories_to_file(CATEGORIES_GASTO_FILE, CATEGORIAS_GASTO)
                    st.success(f"Categoria '{new_gasto}' adicionada.")
                    st.rerun()

    if __name__ == "__main__":
        main()
