import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import uuid
import json
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN

# Helper: safe rerun (works even if experimental API missing)
def safe_rerun():
    """
    Try to rerun the app safely. Prefer st.experimental_rerun() if available.
    If not, increment a session_state counter and call st.stop() to force Streamlit to stop
    the current run and re-render.
    """
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        logging.exception("st.experimental_rerun failed")
    try:
        if hasattr(st, "rerun"):
            st.rerun()
            return
    except Exception:
        logging.exception("st.rerun failed")
    try:
        st.session_state['_safe_rerun_count'] = st.session_state.get('_safe_rerun_count', 0) + 1
    except Exception:
        logging.exception("Could not set _safe_rerun_count in session_state")
    try:
        st.stop()
    except Exception:
        return


# Nome do arquivo para persistência dos dados
DATA_FILE = "dados_custos.csv"
CARDS_FILE = "cartoes.csv"  # armazena cartões: Nome,Bandeira,Dono,DiaFechamento
GOALS_FILE = "metas.json"   # armazena metas por perfil

# --- Funções de Gerenciamento de Categorias ---
CATEGORIES_ENTRADA_FILE = "categorias_entrada.txt"
CATEGORIES_GASTO_FILE = "categorias_gasto.txt"

def load_categories_from_file(file_path, default_categories):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            categories = [line.strip() for line in f if line.strip()]
            return categories if categories else default_categories
    except FileNotFoundError:
        return default_categories

def save_categories_to_file(file_path, categories_list):
    with open(file_path, 'w', encoding='utf-8') as f:
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
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            profiles = [line.strip() for line in f if line.strip()]
            if not profiles:
                return ['Principal']
            return profiles
    except FileNotFoundError:
        return ['Principal']

def save_profiles(profiles_list):
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        for profile in profiles_list:
            f.write(f"{profile}\n")

# --- Funções de Gerenciamento de Cartões ---
def load_cards():
    """Retorna DataFrame com colunas: Nome, Bandeira, Dono, DiaFechamento (int)"""
    if not os.path.exists(CARDS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Bandeira', 'Dono', 'DiaFechamento'])
        df.to_csv(CARDS_FILE, index=False)
        return df
    df = pd.read_csv(CARDS_FILE, dtype={'Nome': str, 'Bandeira': str, 'Dono': str, 'DiaFechamento': 'Int64'})
    return df

def save_cards(df_cards):
    df_cards.to_csv(CARDS_FILE, index=False)

# --- Gerenciamento de metas (arquivo metas.json) ---
def load_goals():
    try:
        with open(GOALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        st.warning(f"Não foi possível carregar metas: {e}")
        return {}

def save_goals(goals):
    try:
        with open(GOALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(goals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Não foi possível salvar metas: {e}")

# --- Função auxiliar: dividir valor em parcelas com centavos distribuídos ---
def split_amount_into_installments(total_value, n_installments):
    """
    Divide total_value (float ou Decimal-compatível) em n_installments partes com 2 casas decimais,
    garantindo que a soma das partes seja igual ao valor total.
    """
    if n_installments <= 0:
        return []

    total = Decimal(str(total_value))
    base = (total / Decimal(n_installments)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    parts = [base for _ in range(n_installments)]
    remainder = total - base * n_installments

    cent = Decimal("0.01")
    i = 0
    while remainder >= cent - Decimal("0.0000001"):
        parts[i] += cent
        remainder -= cent
        i += 1
        if i >= n_installments:
            i = 0

    return [float(p) for p in parts]

# --- UID helpers (internal unique identifier) ---
def _new_uid():
    return str(uuid.uuid4())

# --- Funções de dados (transações) ---
def load_data(profile):
    """
    Carrega arquivo CSV do perfil. Garante colunas novas e preenche UIDs ausentes.
    Mantém a coluna 'UID' internamente.
    """
    filename = f"{profile}_{DATA_FILE}"
    try:
        df = pd.read_csv(filename)
        if not df.empty:
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data']).dt.date
            # garantir colunas novas existam
            for col in ['UID', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas', 'TotalCompra', 'Grupo']:
                if col not in df.columns:
                    df[col] = pd.NA
            if 'UID' in df.columns:
                df['UID'] = df['UID'].fillna('').astype(str)
                for i, val in df['UID'].items():
                    if not val:
                        df.at[i, 'UID'] = _new_uid()
        else:
            cols = ['UID','Data','Tipo','Categoria','Descrição','Valor','PagoComCartao','Cartao','NumParcelas','ParcelaAtual','GerouParcelas','TotalCompra','Grupo']
            df = pd.DataFrame(columns=cols)
        return df
    except FileNotFoundError:
        cols = ['UID','Data','Tipo','Categoria','Descrição','Valor','PagoComCartao','Cartao','NumParcelas','ParcelaAtual','GerouParcelas','TotalCompra','Grupo']
        return pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Erro ao carregar dados do perfil {profile}: {e}")
        return pd.DataFrame(columns=['UID','Data','Tipo','Categoria','Descrição','Valor'])

def save_data(df, profile):
    """
    Salva de forma atômica para evitar corrupção (escreve .tmp e renomeia).
    Persiste também a coluna 'UID'.
    """
    df_copy = df.copy()
    if 'Data' in df_copy.columns and not df_copy.empty:
        df_copy['Data'] = pd.to_datetime(df_copy['Data']).dt.strftime('%Y-%m-%d')
    tmp = f"{profile}_{DATA_FILE}.tmp"
    final = f"{profile}_{DATA_FILE}"
    df_copy.to_csv(tmp, index=False)
    try:
        os.replace(tmp, final)
    except Exception:
        try:
            if os.path.exists(final):
                os.remove(final)
        except Exception:
            pass
        os.replace(tmp, final)

def add_transaction(df, data, tipo, categoria, descricao, valor, profile,
                    pago_com_cartao=False, cartao=None, num_parcelas=None, parcela_atual=None, gerar_parcelas=False):
    """
    Adiciona a transação ao dataframe. Cada linha recebe um UID interno.
    """
    for col in ['UID','PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas', 'TotalCompra', 'Grupo']:
        if col not in df.columns:
            df[col] = pd.NA

    installments_values = None
    num = None
    if pago_com_cartao and num_parcelas:
        try:
            num = int(num_parcelas)
            if num > 1:
                installments_values = split_amount_into_installments(valor, num)
        except Exception:
            installments_values = None
            num = None

    start_parcela = int(parcela_atual) if parcela_atual else 1
    grupo_id = str(uuid.uuid4()) if (pago_com_cartao and num and num > 1) else pd.NA
    total_compra_val = float(valor) if pago_com_cartao else pd.NA

    if installments_values and num:
        idx = max(1, min(start_parcela, num)) - 1
        valor_parcela_atual = installments_values[idx]
    else:
        valor_parcela_atual = float(valor)

    base = {
        'UID': _new_uid(),
        'Data': pd.to_datetime(data).date() if not isinstance(data, date) else data,
        'Tipo': tipo,
        'Categoria': categoria,
        'Descrição': descricao if not (installments_values and num) else f"{descricao} ({start_parcela}/{num})",
        'Valor': float(valor_parcela_atual),
        'PagoComCartao': 'Sim' if pago_com_cartao else 'Não',
        'Cartao': cartao if pago_com_cartao else pd.NA,
        'NumParcelas': int(num) if (pago_com_cartao and num) else pd.NA,
        'ParcelaAtual': int(start_parcela) if (pago_com_cartao and parcela_atual) else pd.NA,
        'GerouParcelas': 'Sim' if gerar_parcelas else 'Não',
        'TotalCompra': total_compra_val,
        'Grupo': grupo_id
    }
    new_rows = [base]

    if pago_com_cartao and gerar_parcelas and installments_values and num and int(num) > 1:
        try:
            for p in range(start_parcela + 1, num + 1):
                offset = p - start_parcela
                new_date = pd.to_datetime(data).date() + relativedelta(months=offset)
                row = base.copy()
                row['UID'] = _new_uid()
                row['Data'] = new_date
                row['ParcelaAtual'] = p
                row['Descrição'] = f"{descricao} ({p}/{num})"
                row['Valor'] = float(installments_values[p - 1])
                row['TotalCompra'] = total_compra_val
                row['Grupo'] = grupo_id
                new_rows.append(row)
        except Exception as e:
            st.warning(f"Não foi possível gerar todas as parcelas automaticamente: {e}")

    df_new = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    save_data(df_new, profile)
    return df_new

# --- Helper: reset de campos relacionados à transação (sidebar e outros locais) ---
def reset_transaction_fields(profile, card_names=None):
    known_prefixes = [
        "data",
        "categoria_select",
        "descricao",
        "valor",
        "pago_cartao",
        "cartao_select",
        "num_parcelas",
        "parcela_atual",
        "gerar_parcelas",
    ]

    tipo_key = f"tipo_select_{profile}"
    tipo_atual = st.session_state.get(tipo_key, "Gasto")

    if tipo_atual == "Entrada":
        default_categoria = CATEGORIAS_ENTRADA[0] if len(CATEGORIAS_ENTRADA) > 0 else ""
    else:
        default_categoria = CATEGORIAS_GASTO[0] if len(CATEGORIAS_GASTO) > 0 else ""

    defaults = {
        "data": lambda: pd.to_datetime(date.today()).date(),
        "categoria_select": lambda: default_categoria,
        "descricao": lambda: "",
        "valor": lambda: 0.0,
        "pago_cartao": lambda: False,
        "cartao_select": lambda: ('Selecione' if (card_names and len(card_names) > 0) else ''),
        "num_parcelas": lambda: 1,
        "parcela_atual": lambda: 1,
        "gerar_parcelas": lambda: False,
    }

    for p in known_prefixes:
        key = f"{p}_{profile}"
        if key in st.session_state:
            try:
                factory = defaults.get(p)
                if factory is None:
                    continue
                st.session_state[key] = factory()
            except Exception:
                logging.exception(f"Falha ao resetar session_state['{key}']")

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Gerenciamento de Custos Pessoais")

# --- Autenticação Básica ---
try:
    secrets = st.secrets
    USERNAME = secrets.get("USERNAME", os.environ.get("APP_USERNAME", "familia"))
    PASSWORD = secrets.get("PASSWORD", os.environ.get("APP_PASSWORD", "cabuloso"))
except Exception:
    USERNAME = os.environ.get("APP_USERNAME", "familia")
    PASSWORD = os.environ.get("APP_PASSWORD", "cabuloso")

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
                safe_rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    # --- Funções de Gráficos ---
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
        if 'Pessoa' not in df_all.columns:
            st.info("Dados não contém informação de perfil para comparação.")
            return
        grouped = df_all.groupby(['Pessoa', 'Tipo'])['Valor'].sum().reset_index()
        fig = px.bar(grouped, x='Pessoa', y='Valor', color='Tipo', barmode='group', title="Comparativo de Entradas e Gastos por Perfil")
        fig.update_layout(template="plotly_white", yaxis_title="Valor (R$)")
        st.plotly_chart(fig, use_container_width=True)

    def plot_spending_vs_goal(resumo_df, meta_gasto, profile):
        if resumo_df.empty:
            st.info("Sem dados para exibir comparação com meta.")
            return
        dfp = resumo_df.reset_index().copy()
        dfp = dfp.sort_values('Ano-Mês')
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dfp['Ano-Mês'], y=dfp.get('Gasto', 0), mode='lines+markers', name='Gasto', line=dict(color='crimson')))
        if meta_gasto is not None:
            fig.add_trace(go.Scatter(x=dfp['Ano-Mês'], y=[meta_gasto]*len(dfp), mode='lines', name='Meta Gasto', line=dict(color='black', dash='dash')))
        fig.update_layout(title=f"Gastos x Meta - {profile}", xaxis_title="Mês", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

        if meta_gasto is not None:
            dfp['Excedeu'] = dfp['Gasto'] > meta_gasto
            excedeu_count = dfp['Excedeu'].sum()
            st.write(f"{excedeu_count} mês(es) superaram a meta de gasto.")

    def plot_sobra_vs_goal(resumo_df, meta_sobra_percent, profile):
        if resumo_df.empty:
            st.info("Sem dados para exibir comparação de sobra com meta.")
            return
        dfp = resumo_df.reset_index().copy()
        dfp = dfp.sort_values('Ano-Mês')
        dfp['Sobra'] = dfp.get('Entrada', 0) - dfp.get('Gasto', 0)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dfp['Ano-Mês'], y=dfp['Sobra'], mode='lines+markers', name='Sobra (Entrada - Gasto)', line=dict(color='green')))
        if meta_sobra_percent is not None:
            dfp['MetaSobra'] = dfp.get('Entrada', 0) * (meta_sobra_percent / 100.0)
            fig.add_trace(go.Scatter(x=dfp['Ano-Mês'], y=dfp['MetaSobra'], mode='lines', name=f'Meta Sobra ({meta_sobra_percent}%)', line=dict(color='black', dash='dash')))
        fig.update_layout(title=f"Sobra x Meta de Sobra - {profile}", xaxis_title="Mês", yaxis_title="Valor (R$)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

        if meta_sobra_percent is not None:
            dfp['AtingiuSobra'] = dfp['Sobra'] >= dfp['MetaSobra']
            atingiu_count = dfp['AtingiuSobra'].sum()
            st.write(f"{atingiu_count} mês(es) atingiram a meta de sobra ({meta_sobra_percent}%).")

    # --- Aba de Perfil (com filtros iguais à Análise Geral) ---
    def profile_tab(profile):
        st.header(f"👤 Perfil: {profile}")

        df_profile = load_data(profile)

        # carregar metas para este perfil
        goals = load_goals()
        profile_goals = goals.get(profile, {})
        meta_gasto_default = profile_goals.get('meta_gasto', None)
        meta_sobra_percent_default = profile_goals.get('meta_sobra_percent', None)

        st.sidebar.header(f"Adicionar Transação ({profile})")
        tipo = st.sidebar.selectbox("Tipo", ["Entrada", "Gasto"], key=f"tipo_select_{profile}")

        # Carregar cartões para seleção
        cards_df = load_cards()
        card_names = cards_df['Nome'].tolist() if not cards_df.empty else []

        # Chaves usadas pelo formulário (padronizadas para o app)
        key_data = f"data_{profile}"
        key_categoria = f"categoria_select_{profile}"
        key_descricao = f"descricao_{profile}"
        key_valor = f"valor_{profile}"
        key_pago_cartao = f"pago_cartao_{profile}"
        key_cartao = f"cartao_select_{profile}"
        key_num_parcelas = f"num_parcelas_{profile}"
        key_parcela_atual = f"parcela_atual_{profile}"
        key_gerar_parcelas = f"gerar_parcelas_{profile}"

        # inicializar session_state com valores padrão caso ainda não existam
        if key_data not in st.session_state:
            st.session_state[key_data] = pd.to_datetime(date.today()).date()
        if key_categoria not in st.session_state:
            categorias_filtradas_init = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO
            st.session_state[key_categoria] = categorias_filtradas_init[0] if categorias_filtradas_init else ""
        if key_descricao not in st.session_state:
            st.session_state[key_descricao] = ""
        if key_valor not in st.session_state:
            st.session_state[key_valor] = 0.0
        if key_pago_cartao not in st.session_state:
            st.session_state[key_pago_cartao] = False
        if key_cartao not in st.session_state:
            st.session_state[key_cartao] = 'Selecione' if card_names else ''
        if key_num_parcelas not in st.session_state:
            st.session_state[key_num_parcelas] = 1
        if key_parcela_atual not in st.session_state:
            st.session_state[key_parcela_atual] = 1
        if key_gerar_parcelas not in st.session_state:
            st.session_state[key_gerar_parcelas] = False

        categorias_filtradas = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO

        # --- FORMULÁRIO: adicionar transação (sidebar) ---
        with st.sidebar.form(f"add_transaction_form_{profile}"):
            data = st.date_input("Data", key=key_data)
            categoria = st.selectbox("Categoria", categorias_filtradas, key=key_categoria)
            descricao = st.text_input("Descrição", key=key_descricao)
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, key=key_valor)

            pago_com_cartao = st.checkbox("Pago com cartão de crédito?", key=key_pago_cartao)
            cartao = None
            num_parcelas = None
            parcela_atual = None
            gerar_parcelas = False
            if pago_com_cartao:
                if card_names:
                    cartao = st.selectbox("Cartão utilizado", ['Selecione'] + card_names, key=key_cartao)
                    if cartao == 'Selecione':
                        cartao = None
                    num_parcelas = st.number_input("Número de parcelas (1 para à vista)", min_value=1, step=1, key=key_num_parcelas)
                    parcela_atual = st.number_input("Parcela atual (ex: 1)", min_value=1, max_value=int(st.session_state.get(key_num_parcelas, 1)), step=1, key=key_parcela_atual)
                    gerar_parcelas = st.checkbox("Gerar automaticamente lançamentos das parcelas futuras?", key=key_gerar_parcelas)
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

                    # RESETAR campos relacionados à transação
                    reset_transaction_fields(profile, card_names=card_names)

                    # Forçar rerun para aplicar os novos valores no formulário e na UI
                    safe_rerun()

        # --- Metas (form separado) ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("Metas (mensal)")

        with st.sidebar.form(f"metas_form_{profile}"):
            meta_gasto = st.number_input("Meta de Gastos mensal (R$)", min_value=0.0, step=10.0, value=float(meta_gasto_default) if meta_gasto_default not in (None, pd.NA) else 0.0)
            meta_sobra_percent = st.number_input("Meta de sobra (% da entrada)", min_value=0.0, max_value=100.0, step=1.0, value=float(meta_sobra_percent_default) if meta_sobra_percent_default not in (None, pd.NA) else 0.0)
            save_meta = st.form_submit_button("Salvar Metas")
            if save_meta:
                goals = load_goals()
                goals[profile] = {
                    'meta_gasto': float(meta_gasto),
                    'meta_sobra_percent': float(meta_sobra_percent)
                }
                save_goals(goals)
                st.success("Metas salvas.")
                safe_rerun()

        if df_profile.empty:
            st.info("Nenhuma transação neste perfil.")
            return

        # --- FILTROS (aplicando o mesmo comportamento da Análise Geral) ---
        st.subheader("📅 Filtros de Análise")
        # Data mínima/máxima do perfil
        min_date = pd.to_datetime(df_profile['Data']).dt.date.min()
        max_date = pd.to_datetime(df_profile['Data']).dt.date.max()
        # campos de filtro com keys únicas por profile (mantêm estado entre reruns)
        start_date = st.date_input("Data Inicial", min_date if pd.notna(min_date) else date.today(), key=f"start_{profile}")
        end_date = st.date_input("Data Final", max_date if pd.notna(max_date) else date.today(), key=f"end_{profile}")

        # filtro por cartão, similar ao geral
        card_options = ['Todos'] + card_names if card_names else ['Todos']
        selected_card = st.selectbox("Filtrar por Cartão (opcional)", card_options, key=f"card_filter_{profile}")

        # aplicar filtros ao dataframe do perfil
        df_filtered = df_profile[
            (pd.to_datetime(df_profile['Data']).dt.date >= pd.to_datetime(start_date).date()) &
            (pd.to_datetime(df_profile['Data']).dt.date <= pd.to_datetime(end_date).date())
        ]
        if selected_card != 'Todos':
            df_filtered = df_filtered[df_filtered['Cartao'] == selected_card]

        # --- Tabela / Editor (aplicar filtros também ao editor) ---
        st.subheader("🧾 Tabela de Transações")
        cols_to_show = [c for c in df_profile.columns if c in ['UID','Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'TotalCompra', 'Grupo']]

        # Não mostrar a coluna UID para o usuário no editor, mas usá-la internamente para merge
        editor_display_cols = [c for c in cols_to_show if c != 'UID']
        # Se quiser exibir apenas o subconjunto filtrado:
        edited_df = st.data_editor(
            df_filtered[editor_display_cols],
            key=f"data_editor_{profile}",
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
                "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "TotalCompra": st.column_config.NumberColumn("TotalCompra (R$)", format="R$ %.2f", disabled=True),
                "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
            }
        )

        if not edited_df.equals(df_filtered[editor_display_cols]):
            # atualizar por UID/heurística no df_full do perfil
            df_full = load_data(profile)
            for _, row in edited_df.iterrows():
                # Tentar encontrar correspondência única no df_full.
                uid = None
                if 'UID' in row.index and pd.notna(row.get('UID')) and row.get('UID'):
                    uid = row.get('UID')

                updated = False
                if uid and 'UID' in df_full.columns:
                    mask = df_full['UID'] == uid
                    if mask.any():
                        for col in row.index:
                            if col in df_full.columns:
                                df_full.loc[mask, col] = row[col]
                        updated = True
                else:
                    cond = pd.Series([True] * len(df_full))
                    for col in ['Data', 'Descrição', 'Valor', 'Cartao', 'ParcelaAtual', 'NumParcelas']:
                        if col in row.index and col in df_full.columns:
                            cond = cond & (df_full[col].astype(str) == str(row[col]))
                    matches = df_full[cond]
                    if len(matches) == 1:
                        idx = matches.index[0]
                        for col in row.index:
                            if col in df_full.columns:
                                df_full.at[idx, col] = row[col]
                        updated = True

                if not updated:
                    new_row = row.to_dict()
                    new_row['UID'] = _new_uid()
                    for k in ['UID','Data','Tipo','Categoria','Descrição','Valor','PagoComCartao','Cartao','NumParcelas','ParcelaAtual','GerouParcelas','TotalCompra','Grupo']:
                        if k not in new_row:
                            new_row[k] = pd.NA
                    df_full = pd.concat([df_full, pd.DataFrame([new_row])], ignore_index=True)

            save_data(df_full, profile)
            st.success("Transações atualizadas com sucesso!")
            safe_rerun()

        # --- Gráficos e Resumo (usando df_filtered) ---
        st.markdown("---")
        st.subheader("📈 Tendência de Gastos e Entradas")
        plot_trend_chart(df_filtered, title=f"Tendência - {profile}")

        st.subheader("🍕 Gastos por Categoria")
        plot_category_chart(df_filtered[df_filtered['Tipo'] == 'Gasto'])

        st.subheader("📊 Resumo Mensal")
        df_filtered_local = df_filtered.copy()
        df_filtered_local['Ano-Mês'] = pd.to_datetime(df_filtered_local['Data']).dt.to_period('M').astype(str)
        resumo = df_filtered_local.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().unstack(fill_value=0)
        if 'Entrada' not in resumo.columns:
            resumo['Entrada'] = 0.0
        if 'Gasto' not in resumo.columns:
            resumo['Gasto'] = 0.0
        resumo['Saldo'] = resumo['Entrada'] - resumo['Gasto']
        st.dataframe(resumo)

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
        min_date = pd.to_datetime(df_all['Data']).dt.date.min()
        max_date = pd.to_datetime(df_all['Data']).dt.date.max()
        start_date = st.sidebar.date_input("Data Inicial", min_date if pd.notna(min_date) else date.today())
        end_date = st.sidebar.date_input("Data Final", max_date if pd.notna(max_date) else date.today())
        cards_df = load_cards()
        card_options = ['Todos'] + cards_df['Nome'].tolist() if not cards_df.empty else ['Todos']
        selected_card = st.sidebar.selectbox("Filtrar por Cartão (opcional)", card_options)
        df_filtered = df_all[(pd.to_datetime(df_all['Data']).dt.date >= pd.to_datetime(start_date).date()) & (pd.to_datetime(df_all['Data']).dt.date <= pd.to_datetime(end_date).date())]
        if selected_card != 'Todos':
            df_filtered = df_filtered[df_filtered['Cartao'] == selected_card]

        st.write(f"Período selecionado: **{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}**")

        # --- Tabela primeiro ---
        st.subheader("🧾 Tabela de Transações (Edição e Exclusão)")

        # não incluir 'UID' no editor para o usuário
        cols_to_show = [c for c in df_filtered.columns if c in ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'TotalCompra', 'Grupo']]
        display_df = df_filtered[cols_to_show + ['Pessoa']] if 'Pessoa' in df_filtered.columns else df_filtered[cols_to_show]

        column_config = {
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
            "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "TotalCompra": st.column_config.NumberColumn("TotalCompra (R$)", format="R$ %.2f", disabled=True),
            "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
        }

        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config=column_config
        )

        if not edited_df.equals(display_df):
            # atualizar por UID por perfil, evitando sobrescrever linhas não exibidas
            for profile in profiles:
                if 'Pessoa' in edited_df.columns:
                    edited_for_profile = edited_df[edited_df['Pessoa'] == profile].drop(columns=['Pessoa'])
                else:
                    edited_for_profile = edited_df
                if edited_for_profile.empty:
                    continue
                df_full = load_data(profile)
                # para cada linha editada, tentar localizar pelo UID combinando com outras colunas na fonte original
                for _, row in edited_for_profile.iterrows():
                    uid = None
                    if 'UID' in row.index and pd.notna(row['UID']) and row['UID']:
                        uid = row['UID']
                    updated = False
                    if uid:
                        mask = df_full['UID'] == uid
                        if mask.any():
                            for col in row.index:
                                if col in df_full.columns:
                                    df_full.loc[mask, col] = row[col]
                            updated = True
                    else:
                        cond = pd.Series([True] * len(df_full))
                        for col in ['Data', 'Valor', 'Descrição', 'Cartao', 'ParcelaAtual', 'NumParcelas']:
                            if col in row.index and col in df_full.columns:
                                cond = cond & (df_full[col].astype(str) == str(row[col]))
                        matches = df_full[cond]
                        if len(matches) == 1:
                            idx = matches.index[0]
                            for col in row.index:
                                if col in df_full.columns:
                                    df_full.at[idx, col] = row[col]
                            updated = True
                    if not updated:
                        new_row = row.to_dict()
                        new_row['UID'] = _new_uid()
                        for k in ['UID','Data','Tipo','Categoria','Descrição','Valor','PagoComCartao','Cartao','NumParcelas','ParcelaAtual','GerouParcelas','TotalCompra','Grupo']:
                            if k not in new_row:
                                new_row[k] = pd.NA
                        df_full = pd.concat([df_full, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df_full, profile)
            st.success("Transações atualizadas com sucesso!")
            safe_rerun()

        # --- Gráficos depois ---
        st.markdown("---")
        st.subheader("📈 Gráfico de Tendência")
        plot_trend_chart(df_filtered)

        st.subheader("🍕 Distribuição de Gastos por Categoria")
        plot_category_chart(df_filtered[df_filtered['Tipo'] == 'Gasto'])

        st.subheader("👥 Comparativo entre Perfis")
        plot_profile_comparison(df_filtered)

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
                    safe_rerun()
                else:
                    st.warning("Este perfil já existe.")

        st.subheader("Remover Perfil")
        profile_to_remove = st.selectbox("Selecione o Perfil para Remover", profiles)
        if st.button("Remover Perfil"):
            profiles.remove(profile_to_remove)
            save_profiles(profiles)
            st.success(f"Perfil '{profile_to_remove}' removido com sucesso!")
            safe_rerun()

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
                    safe_rerun()

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
                    safe_rerun()

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
                    if nome in cards_df['Nome'].values:
                        cards_df.loc[cards_df['Nome'] == nome, ['Bandeira', 'Dono', 'DiaFechamento']] = [bandeira, dono, int(dia_fech)]
                        save_cards(cards_df)
                        st.success("Cartão atualizado.")
                        safe_rerun()
                    else:
                        new_row = pd.DataFrame([{'Nome': nome, 'Bandeira': bandeira, 'Dono': dono, 'DiaFechamento': int(dia_fech)}])
                        cards_df = pd.concat([cards_df, new_row], ignore_index=True)
                        save_cards(cards_df)
                        st.success("Cartão adicionado.")
                        safe_rerun()

        st.subheader("Remover Cartão")
        if not cards_df.empty:
            card_to_remove = st.selectbox("Selecione o cartão para remover", cards_df['Nome'].tolist())
            if st.button("Remover Cartão"):
                cards_df = cards_df[cards_df['Nome'] != card_to_remove]
                save_cards(cards_df)
                st.success("Cartão removido.")
                safe_rerun()

    if __name__ == "__main__":
        main()
