import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import date
from dateutil.relativedelta import relativedelta

# Nome do arquivo para persistência dos dados
DATA_FILE = "dados_custos.csv"
CARDS_FILE = "cartoes.csv"  # armazena cartões: Nome,Bandeira,Dono,DiaFechamento

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

# --- Funções de Gerenciamento de Cartões ---
def load_cards():
    """Retorna DataFrame com colunas: Nome, Bandeira, Dono, DiaFechamento (int)"""
    if not os.path.exists(CARDS_FILE):
        # cria arquivo vazio
        df = pd.DataFrame(columns=['Nome', 'Bandeira', 'Dono', 'DiaFechamento'])
        df.to_csv(CARDS_FILE, index=False)
        return df
    df = pd.read_csv(CARDS_FILE, dtype={'Nome': str, 'Bandeira': str, 'Dono': str, 'DiaFechamento': 'Int64'})
    return df

def save_cards(df_cards):
    df_cards.to_csv(CARDS_FILE, index=False)

# --- Funções de dados (transações) ---
def load_data(profile):
    try:
        df = pd.read_csv(f"{profile}_{DATA_FILE}")
        if not df.empty:
            df['Data'] = pd.to_datetime(df['Data']).dt.date
        return df
    except FileNotFoundError:
        # colunas novas relacionadas a cartão adicionadas ao schema
        cols = ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas']
        return pd.DataFrame(columns=cols)

def save_data(df, profile):
    # garantir formato de data serializável
    df_copy = df.copy()
    if 'Data' in df_copy.columns:
        df_copy['Data'] = pd.to_datetime(df_copy['Data']).dt.strftime('%Y-%m-%d')
    df_copy.to_csv(f"{profile}_{DATA_FILE}", index=False)

def add_transaction(df, data, tipo, categoria, descricao, valor, profile,
                    pago_com_cartao=False, cartao=None, num_parcelas=None, parcela_atual=None, gerar_parcelas=False):
    """
    Adiciona a transação ao dataframe. Se gerar_parcelas=True e num_parcelas>1,
    gera automaticamente linhas adicionais com datas incrementadas mensalmente.
    """
    # assegura colunas
    for col in ['PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas']:
        if col not in df.columns:
            df[col] = pd.NA

    # linha inicial (parcela atual informada)
    base = {
        'Data': pd.to_datetime(data).date() if not isinstance(data, date) else data,
        'Tipo': tipo,
        'Categoria': categoria,
        'Descrição': descricao,
        'Valor': float(valor),
        'PagoComCartao': 'Sim' if pago_com_cartao else 'Não',
        'Cartao': cartao if pago_com_cartao else pd.NA,
        'NumParcelas': int(num_parcelas) if (pago_com_cartao and num_parcelas) else pd.NA,
        'ParcelaAtual': int(parcela_atual) if (pago_com_cartao and parcela_atual) else pd.NA,
        'GerouParcelas': 'Sim' if gerar_parcelas else 'Não'
    }
    new_rows = [base]

    # se for cartão e o usuário optar por gerar parcelas automaticamente:
    if pago_com_cartao and gerar_parcelas and num_parcelas and int(num_parcelas) > 1:
        try:
            num = int(num_parcelas)
            start_parcela = int(parcela_atual) if parcela_atual else 1
            # gerar para as parcelas restantes (a partir de parcela_atual+1 até num)
            for p in range(start_parcela + 1, num + 1):
                new_date = pd.to_datetime(data).date() + relativedelta(months=(p - start_parcela))
                row = base.copy()
                row['Data'] = new_date
                row['ParcelaAtual'] = p
                # opcional: indicar no descr. que é parcela X/N
                row['Descrição'] = f"{descricao} ({p}/{num})"
                new_rows.append(row)
        except Exception as e:
            # se algo falhar, não interrompe; apenas não gera parcelas
            st.warning(f"Não foi possível gerar todas as parcelas automaticamente: {e}")

    df_new = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    save_data(df_new, profile)
    return df_new

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
        df_local = df.copy()
        df_local['Ano-Mês'] = pd.to_datetime(df_local['Data']).dt.to_period('M').astype(str)
        grouped = df_local.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().reset_index()
        fig = px.line(grouped, x='Ano-Mês', y='Valor', color='Tipo', markers=True, title=title)
        fig.update_layout(xaxis_title="Mês", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    def plot_category_chart(df, title="Distribuição por Categoria"):
        if df.empty:
            st.info("Sem dados para exibir a distribuição de categorias.")
            return
        grouped = df.groupby('Categoria')['Valor'].sum().reset_index().sort_values('Valor', ascending=False)
        fig = px.bar(grouped, x='Categoria', y='Valor', text_auto=True, title=title)
        fig.update_layout(xaxis_title="", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    def plot_profile_comparison(df_all):
        if df_all.empty:
            st.info("Sem dados para comparação de perfis.")
            return
        grouped = df_all.groupby(['Pessoa', 'Tipo'])['Valor'].sum().reset_index()
        fig = px.bar(grouped, x='Pessoa', y='Valor', color='Tipo', barmode='group', title="Comparativo de Entradas e Gastos por Perfil")
        fig.update_layout(template="plotly_white", yaxis_title="Valor (R$)")
        st.plotly_chart(fig, use_container_width=True)

    # --- Interface Principal ---
    def main():
        st.title("💳 Gerenciamento de Custos Pessoais (com Cartões)")

        profiles = load_profiles()
        cards_df = load_cards()
        tab_titles = ["Análise Geral"] + profiles + ["Gerenciamento de Perfis", "Gerenciamento de Categorias", "Gerenciamento de Cartões"]
        tabs = st.tabs(tab_titles)

        with tabs[0]:
            general_analysis_tab(profiles)

        for i, profile in enumerate(profiles):
            with tabs[i + 1]:
                profile_tab(profile)

        with tabs[-3]:
            manage_profiles_tab()

        with tabs[-2]:
            manage_categories_tab()

        with tabs[-1]:
            manage_cards_tab()

    # --- Análise Geral ---
    def general_analysis_tab(profiles):
        st.header("📊 Análise Geral de Todos os Perfis")

        all_data = []
        for profile in profiles:
            df_profile = load_data(profile)
            if not df_profile.empty:
                df_profile = df_profile.copy()
                df_profile["Pessoa"] = profile
                all_data.append(df_profile)

        if not all_data:
            st.info("Nenhuma transação cadastrada.")
            return

        df_all = pd.concat(all_data, ignore_index=True)

        # --- Filtros ---
        st.sidebar.subheader("Filtros - Análise Geral")
        start_date = st.sidebar.date_input("Data Inicial", pd.to_datetime(df_all['Data']).dt.date.min())
        end_date = st.sidebar.date_input("Data Final", pd.to_datetime(df_all['Data']).dt.date.max())
        # filtro por cartão opcional
        cards_df = load_cards()
        card_options = ['Todos'] + cards_df['Nome'].tolist() if not cards_df.empty else ['Todos']
        selected_card = st.sidebar.selectbox("Filtrar por Cartão (opcional)", card_options)
        df_filtered = df_all[(pd.to_datetime(df_all['Data']).dt.date >= pd.to_datetime(start_date).date()) & (pd.to_datetime(df_all['Data']).dt.date <= pd.to_datetime(end_date).date())]
        if selected_card != 'Todos':
            df_filtered = df_filtered[df_filtered['Cartao'] == selected_card]

        st.write(f"Período selecionado: **{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}**")

        # --- Tabela primeiro ---
        st.subheader("🧾 Tabela de Transações (Edição e Exclusão)")

        # mostrar colunas adicionais relacionadas a cartão
        cols_to_show = [c for c in df_filtered.columns if c in ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual']]
        edited_df = st.data_editor(
            df_filtered[cols_to_show + ['Pessoa']] if 'Pessoa' in df_filtered.columns else df_filtered[cols_to_show],
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            }
        )

        if not edited_df.equals(df_filtered[cols_to_show + ['Pessoa']] if 'Pessoa' in df_filtered.columns else df_filtered[cols_to_show]):
            # salvar de volta por perfil
            for profile in profiles:
                # pega linhas que pertencem ao perfil
                if 'Pessoa' in edited_df.columns:
                    df_profile_updated = edited_df[edited_df["Pessoa"] == profile].drop(columns=["Pessoa"])
                else:
                    df_profile_updated = edited_df
                # carregar antigo e salvar
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

        # Carregar cartões para seleção
        cards_df = load_cards()
        card_names = cards_df['Nome'].tolist() if not cards_df.empty else []

        with st.sidebar.form(f"add_transaction_form_{profile}"):
            data = st.date_input("Data", value=pd.to_datetime(date.today()).date())
            categorias_filtradas = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO
            categoria = st.selectbox("Categoria", categorias_filtradas, key=f"categoria_select_{profile}")
            descricao = st.text_input("Descrição")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)

            pago_com_cartao = st.checkbox("Pago com cartão de crédito?", key=f"pago_cartao_{profile}")
            cartao = None
            num_parcelas = None
            parcela_atual = None
            gerar_parcelas = False
            if pago_com_cartao:
                if card_names:
                    cartao = st.selectbox("Cartão utilizado", ['Selecione'] + card_names, key=f"cartao_select_{profile}")
                    if cartao == 'Selecione':
                        cartao = None
                    num_parcelas = st.number_input("Número de parcelas (1 para à vista)", min_value=1, step=1, key=f"num_parcelas_{profile}")
                    parcela_atual = st.number_input("Parcela atual (ex: 1)", min_value=1, max_value=int(num_parcelas) if num_parcelas else 1, value=1, step=1, key=f"parcela_atual_{profile}")
                    gerar_parcelas = st.checkbox("Gerar automaticamente lançamentos das parcelas futuras?", key=f"gerar_parcelas_{profile}")
                else:
                    st.info("Nenhum cartão cadastrado. Cadastre um cartão na aba 'Gerenciamento de Cartões' antes de usar esta opção.")

            submitted = st.form_submit_button("Adicionar")
            if submitted:
                # validações básicas
                if pago_com_cartao and not cartao:
                    st.warning("Selecione um cartão válido ou desmarque 'Pago com cartão'.")
                else:
                    df_profile = add_transaction(df_profile, data, tipo, categoria, descricao, valor, profile,
                                                 pago_com_cartao, cartao, num_parcelas, parcela_atual, gerar_parcelas)
                    st.success("Transação adicionada com sucesso!")
                    st.rerun()

        if df_profile.empty:
            st.info("Nenhuma transação neste perfil.")
            return

        # --- Filtros de data ---
        st.subheader("📅 Filtros de Análise")
        start_date = st.date_input("Data Inicial", pd.to_datetime(df_profile['Data']).dt.date.min(), key=f"start_{profile}")
        end_date = st.date_input("Data Final", pd.to_datetime(df_profile['Data']).dt.date.max(), key=f"end_{profile}")
        df_filtered = df_profile[(pd.to_datetime(df_profile['Data']).dt.date >= pd.to_datetime(start_date).date()) & (pd.to_datetime(df_profile['Data']).dt.date <= pd.to_datetime(end_date).date())]

        # --- Tabela primeiro ---
        st.subheader("🧾 Tabela de Transações")

        cols_to_show = [c for c in df_profile.columns if c in ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual']]
        edited_df = st.data_editor(
            df_profile[cols_to_show],
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

        if not edited_df.equals(df_profile[cols_to_show]):
            save_data(edited_df, profile)
            st.success("Transações atualizadas com sucesso!")
            st.rerun()

        # --- Gráficos depois ---
        st.markdown("---")
        st.subheader("📈 Tendência de Gastos e Entradas")
        plot_trend_chart(df_filtered, title=f"Tendência - {profile}")

        st.subheader("🍕 Gastos por Categoria")
        plot_category_chart(df_filtered[df_filtered['Tipo'] == 'Gasto'], title=f"Distribuição de Gastos - {profile}")

        df_filtered_local = df_filtered.copy()
        df_filtered_local['Ano-Mês'] = pd.to_datetime(df_filtered_local['Data']).dt.to_period('M').astype(str)
        resumo = df_filtered_local.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().unstack(fill_value=0)
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

    # --- Aba de Cartões ---
    def manage_cards_tab():
        st.header("💳 Gerenciamento de Cartões")

        cards_df = load_cards()
        st.subheader("Cartões Cadastrados")
        if cards_df.empty:
            st.info("Nenhum cartão cadastrado.")
        else:
            display_df = cards_df.copy()
            display_df['DiaFechamento'] = display_df['DiaFechamento'].astype('Int64')
            st.dataframe(display_df)

        st.markdown("---")
        st.subheader("Adicionar / Atualizar Cartão")
        with st.form("add_card_form"):
            nome = st.text_input("Nome do Cartão (ex: 'Nubank Visa')")
            bandeira = st.text_input("Bandeira (ex: Visa, MasterCard, Elo)")
            profiles = load_profiles()
            dono = st.selectbox("Dono do Cartão (perfil)", profiles)
            dia_fech = st.number_input("Dia de fechamento da fatura (1-31)", min_value=1, max_value=31, step=1)
            submitted_card = st.form_submit_button("Salvar Cartão")
            if submitted_card:
                if not nome:
                    st.warning("Insira o nome do cartão.")
                else:
                    # se já existe, atualiza
                    if nome in cards_df['Nome'].values:
                        cards_df.loc[cards_df['Nome'] == nome, ['Bandeira', 'Dono', 'DiaFechamento']] = [bandeira, dono, int(dia_fech)]
                        save_cards(cards_df)
                        st.success("Cartão atualizado.")
                        st.rerun()
                    else:
                        new_row = pd.DataFrame([{'Nome': nome, 'Bandeira': bandeira, 'Dono': dono, 'DiaFechamento': int(dia_fech)}])
                        cards_df = pd.concat([cards_df, new_row], ignore_index=True)
                        save_cards(cards_df)
                        st.success("Cartão adicionado.")
                        st.rerun()

        st.subheader("Remover Cartão")
        if not cards_df.empty:
            card_to_remove = st.selectbox("Selecione o cartão para remover", cards_df['Nome'].tolist())
            if st.button("Remover Cartão"):
                cards_df = cards_df[cards_df['Nome'] != card_to_remove]
                save_cards(cards_df)
                st.success("Cartão removido.")
                st.rerun()

    if __name__ == "__main__":
        main()
