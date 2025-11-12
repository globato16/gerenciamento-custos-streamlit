import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import uuid
import json
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN

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
        # cria arquivo vazio
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
    garantindo que a soma das partes seja igual ao valor total (distribui os centavos extras nas primeiras parcelas).
    Retorna lista de floats (comprimento n_installments).
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

# --- Funções de dados (transações) ---
def load_data(profile):
    filename = f"{profile}_{DATA_FILE}"
    try:
        df = pd.read_csv(filename)
        if not df.empty:
            # normaliza Data
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data']).dt.date
            # garantir colunas novas existam para compatibilidade com versões antigas
            for col in ['PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas', 'TotalCompra', 'Grupo']:
                if col not in df.columns:
                    df[col] = pd.NA
        return df
    except FileNotFoundError:
        # colunas novas relacionadas a cartão adicionadas ao schema
        cols = ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao',
                'NumParcelas', 'ParcelaAtual', 'GerouParcelas', 'TotalCompra', 'Grupo']
        return pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Erro ao carregar dados do perfil {profile}: {e}")
        return pd.DataFrame()

def save_data(df, profile):
    # garantir formato de data serializável
    df_copy = df.copy()
    if 'Data' in df_copy.columns and not df_copy.empty:
        df_copy['Data'] = pd.to_datetime(df_copy['Data']).dt.strftime('%Y-%m-%d')
    df_copy.to_csv(f"{profile}_{DATA_FILE}", index=False)

def add_transaction(df, data, tipo, categoria, descricao, valor, profile,
                    pago_com_cartao=False, cartao=None, num_parcelas=None, parcela_atual=None, gerar_parcelas=False):
    """
    Adiciona a transação ao dataframe. Se gerar_parcelas=True e num_parcelas>1,
    gera automaticamente linhas adicionais com datas incrementadas mensalmente.
    Ajustes:
      - quando lançado com cartão parcelado, cada parcela recebe o valor = total / N (com centavos distribuídos)
      - adiciona coluna 'TotalCompra' com o valor total da compra (quando aplicável)
      - adiciona coluna 'Grupo' com um UUID para ligar parcelas da mesma compra
    """
    # assegura colunas
    for col in ['PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas', 'TotalCompra', 'Grupo']:
        if col not in df.columns:
            df[col] = pd.NA

    # preparar valores de parcela se for parcelado
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

    # parcela atual (índice 1..N)
    start_parcela = int(parcela_atual) if parcela_atual else 1

    # Grupo: somente quando há parcelamento (num>1) e pagamento com cartão
    grupo_id = str(uuid.uuid4()) if (pago_com_cartao and num and num > 1) else pd.NA

    # TotalCompra: registrar o valor total da compra quando pago com cartão (parcelado ou não), senão pd.NA
    total_compra_val = float(valor) if pago_com_cartao else pd.NA

    # valor para a parcela atual (se parcelado) ou valor total se não for parcelado
    if installments_values and num:
        idx = max(1, min(start_parcela, num)) - 1
        valor_parcela_atual = installments_values[idx]
    else:
        valor_parcela_atual = float(valor)

    # linha inicial (parcela atual informada)
    base = {
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

    # se for cartão e o usuário optar por gerar parcelas automaticamente:
    if pago_com_cartao and gerar_parcelas and installments_values and num and int(num) > 1:
        try:
            # gerar para as parcelas restantes (a partir de parcela_atual+1 até num)
            for p in range(start_parcela + 1, num + 1):
                offset = p - start_parcela
                new_date = pd.to_datetime(data).date() + relativedelta(months=offset)
                row = base.copy()
                row['Data'] = new_date
                row['ParcelaAtual'] = p
                row['Descrição'] = f"{descricao} ({p}/{num})"
                # ajustar valor da parcela p (index p-1)
                row['Valor'] = float(installments_values[p - 1])
                # manter TotalCompra e Grupo iguais
                row['TotalCompra'] = total_compra_val
                row['Grupo'] = grupo_id
                new_rows.append(row)
        except Exception as e:
            st.warning(f"Não foi possível gerar todas as parcelas automaticamente: {e}")

    # Observação: se o usuário NÃO optou por gerar_parcelas, registramos apenas a parcela atual com o valor da parcela (não duplicamos o total).
    df_new = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    save_data(df_new, profile)
    return df_new

# --- Helper: reset de campos relacionados à transação (sidebar e outros locais) ---
def reset_transaction_fields(profile, card_names=None):
    """
    Zera/define valores padrão para todas as chaves de session_state relacionadas ao formulário de transação.
    Procura por keys que terminam com _{profile} e aplica padrão por prefixo.
    """
    suffix = f"_{profile}"
    keys_to_reset = [k for k in list(st.session_state.keys()) if k.endswith(suffix)]

    # obter tipo atual (se existir) para escolher categoria padrão correta
    tipo_key = f"tipo_select_{profile}"
    tipo_atual = st.session_state.get(tipo_key, "Gasto")

    # categoria padrão conforme tipo
    if tipo_atual == "Entrada":
        default_categoria = CATEGORIAS_ENTRADA[0] if len(CATEGORIAS_ENTRADA) > 0 else ""
    else:
        default_categoria = CATEGORIAS_GASTO[0] if len(CATEGORIAS_GASTO) > 0 else ""

    for key in keys_to_reset:
        # detecta prefixos conhecidos e atribui valor padrão apropriado
        if key.startswith("data_"):
            st.session_state[key] = pd.to_datetime(date.today()).date()
        elif key.startswith("categoria_select_"):
            st.session_state[key] = default_categoria
        elif key.startswith("descricao_"):
            st.session_state[key] = ""
        elif key.startswith("valor_"):
            st.session_state[key] = 0.0
        elif key.startswith("pago_cartao_"):
            st.session_state[key] = False
        elif key.startswith("cartao_select_"):
            st.session_state[key] = 'Selecione' if (card_names and len(card_names) > 0) else ''
        elif key.startswith("num_parcelas_"):
            st.session_state[key] = 1
        elif key.startswith("parcela_atual_"):
            st.session_state[key] = 1
        elif key.startswith("gerar_parcelas_"):
            st.session_state[key] = False
        else:
            # fallback: limpar valores genéricos
            cur = st.session_state.get(key, None)
            if isinstance(cur, bool):
                st.session_state[key] = False
            elif isinstance(cur, (int, float)):
                st.session_state[key] = 0
            else:
                st.session_state[key] = ""

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Gerenciamento de Custos Pessoais")

# --- Autenticação Básica ---
# Recomendo mover USERNAME/PASSWORD para st.secrets em produção.
try:
    # Tentar acessar st.secrets; pode lançar StreamlitSecretNotFoundError se não houver secrets configurado
    secrets = st.secrets
    USERNAME = secrets.get("USERNAME", os.environ.get("APP_USERNAME", "familia"))
    PASSWORD = secrets.get("PASSWORD", os.environ.get("APP_PASSWORD", "cabuloso"))
except Exception:
    # Fallback para variáveis de ambiente ou valores padrão
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
                st.rerun()
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

    # Novas funções de plot para metas
    def plot_spending_vs_goal(resumo_df, meta_gasto, profile):
        """
        resumo_df: DataFrame com índice 'Ano-Mês' e colunas 'Entrada' e 'Gasto' (já calculado)
        meta_gasto: float ou None
        """
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

        # resumo textual
        if meta_gasto is not None:
            dfp['Excedeu'] = dfp['Gasto'] > meta_gasto
            excedeu_count = dfp['Excedeu'].sum()
            st.write(f"{excedeu_count} mês(es) superaram a meta de gasto.")

    def plot_sobra_vs_goal(resumo_df, meta_sobra_percent, profile):
        """
        mostra a sobra (Entrada - Gasto) e a meta de sobra (meta_percent% da Entrada) por mês.
        """
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

        # resumo textual
        if meta_sobra_percent is not None:
            dfp['AtingiuSobra'] = dfp['Sobra'] >= dfp['MetaSobra']
            atingiu_count = dfp['AtingiuSobra'].sum()
            st.write(f"{atingiu_count} mês(es) atingiram a meta de sobra ({meta_sobra_percent}%).")

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

        # mostrar colunas adicionais relacionadas a cartão, incluindo TotalCompra e Grupo (apenas leitura)
        cols_to_show = [c for c in df_filtered.columns if c in ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'TotalCompra', 'Grupo']]
        column_config = {
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
            "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "TotalCompra": st.column_config.NumberColumn("TotalCompra (R$)", format="R$ %.2f", disabled=True),
            "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
        }

        display_df = df_filtered[cols_to_show + ['Pessoa']] if 'Pessoa' in df_filtered.columns else df_filtered[cols_to_show]
        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config=column_config
        )

        if not edited_df.equals(display_df):
            # salvar de volta por perfil (atenção para não sobrescrever linhas fora do filtro)
            for profile in profiles:
                # pega linhas que pertencem ao perfil
                if 'Pessoa' in edited_df.columns:
                    df_profile_updated = edited_df[edited_df["Pessoa"] == profile].drop(columns=["Pessoa"])
                else:
                    df_profile_updated = edited_df
                # carregar antigo e salvar (atenção: essa abordagem sobrescreve o arquivo do perfil com as linhas apresentadas;
                # para evitar perda de dados, ideal seria mapear por índice/ID — mantive a atual por compatibilidade com seu fluxo)
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

        with st.sidebar.form(f"add_transaction_form_{profile}"):
            data = st.date_input("Data", value=st.session_state[key_data], key=key_data)
            categoria = st.selectbox("Categoria", categorias_filtradas, index=categorias_filtradas.index(st.session_state.get(key_categoria)) if st.session_state.get(key_categoria) in categorias_filtradas else 0, key=key_categoria)
            descricao = st.text_input("Descrição", value=st.session_state[key_descricao], key=key_descricao)
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, value=float(st.session_state[key_valor]), key=key_valor)

            pago_com_cartao = st.checkbox("Pago com cartão de crédito?", value=st.session_state[key_pago_cartao], key=key_pago_cartao)
            cartao = None
            num_parcelas = None
            parcela_atual = None
            gerar_parcelas = False
            if pago_com_cartao:
                if card_names:
                    cartao = st.selectbox("Cartão utilizado", ['Selecione'] + card_names, index=(0 if st.session_state[key_cartao] == 'Selecione' else (card_names.index(st.session_state[key_cartao]) + 1 if st.session_state[key_cartao] in card_names else 0)), key=key_cartao)
                    if cartao == 'Selecione':
                        cartao = None
                    num_parcelas = st.number_input("Número de parcelas (1 para à vista)", min_value=1, step=1, value=int(st.session_state[key_num_parcelas]), key=key_num_parcelas)
                    parcela_atual = st.number_input("Parcela atual (ex: 1)", min_value=1, max_value=int(num_parcelas) if num_parcelas else 1, value=int(st.session_state[key_parcela_atual]), step=1, key=key_parcela_atual)
                    gerar_parcelas = st.checkbox("Gerar automaticamente lançamentos das parcelas futuras?", value=st.session_state[key_gerar_parcelas], key=key_gerar_parcelas)
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

                    # RESETAR todos os campos relacionados à transação (sidebar e quaisquer outros campos que usam as mesmas keys)
                    reset_transaction_fields(profile, card_names=card_names)

                    # Forçar rerun para aplicar os novos valores no formulário e na UI
                    st.experimental_rerun()

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

        cols_to_show = [c for c in df_profile.columns if c in ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'TotalCompra', 'Grupo']]
        column_config = {
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=['Entrada', 'Gasto']),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=TODAS_CATEGORIAS),
            "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "TotalCompra": st.column_config.NumberColumn("TotalCompra (R$)", format="R$ %.2f", disabled=True),
            "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
        }
        edited_df = st.data_editor(
            df_profile[cols_to_show],
            key=f"data_editor_{profile}",
            use_container_width=True,
            num_rows="dynamic",
            column_config=column_config
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

        # --- Resumo mensal para metas e gráficos de comparação ---
        df_filtered_local = df_filtered.copy()
        df_filtered_local['Ano-Mês'] = pd.to_datetime(df_filtered_local['Data']).dt.to_period('M').astype(str)

        resumo = df_filtered_local.groupby(['Ano-Mês', 'Tipo'])['Valor'].sum().unstack(fill_value=0)
        # garantir colunas Entrada/Gasto existam
        if 'Entrada' not in resumo.columns:
            resumo['Entrada'] = 0.0
        if 'Gasto' not in resumo.columns:
            resumo['Gasto'] = 0.0
        resumo['Saldo'] = resumo['Entrada'] - resumo['Gasto']

        st.subheader("📊 Resumo Mensal")
        st.dataframe(resumo)

        # carregar metas atuais (após possível edição)
        goals = load_goals()
        profile_goals = goals.get(profile, {})
        meta_gasto_val = profile_goals.get('meta_gasto', None)
        meta_sobra_percent_val = profile_goals.get('meta_sobra_percent', None)

        # mostrar metas atuais + botão de download do metas.json
        with st.expander("Metas atuais"):
            st.write(f"Meta de Gastos mensal: R$ {meta_gasto_val if meta_gasto_val not in (None, pd.NA) else 'Não definida'}")
            st.write(f"Meta de sobra: {meta_sobra_percent_val if meta_sobra_percent_val not in (None, pd.NA) else 'Não definida'} % da entrada")
            # botão para download do arquivo metas.json
            if os.path.exists(GOALS_FILE):
                with open(GOALS_FILE, "rb") as f:
                    metas_bytes = f.read()
                st.download_button(
                    label="Download metas.json",
                    data=metas_bytes,
                    file_name="metas.json",
                    mime="application/json"
                )
            else:
                st.info("Arquivo metas.json não encontrado no diretório do app.")

        # gráficos de comparação com metas
        plot_spending_vs_goal(resumo, meta_gasto_val if meta_gasto_val not in (None, pd.NA) else None, profile)
        plot_sobra_vs_goal(resumo, meta_sobra_percent_val if meta_sobra_percent_val not in (None, pd.NA) else None, profile)

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
            # Atenção: remover o perfil não remove automaticamente o arquivo de dados associado.
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
