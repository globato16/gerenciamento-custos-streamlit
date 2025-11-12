import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import calendar
import plotly.graph_objects as go

# ====== Configurações de arquivos ======
DATA_FILE = "dados_custos.csv"           # prefixado por perfil: <perfil>_dados_custos.csv
CARDS_FILE = "cartoes.csv"               # armazena cartões: Nome,Bandeira,Dono,DiaFechamento,DiaVencimento
CONFIG_FILE = "config_alertas.txt"       # JSON com alertas persistidos
CATEGORIES_ENTRADA_FILE = "categorias_entrada.txt"
CATEGORIES_GASTO_FILE = "categorias_gasto.txt"
PROFILES_FILE = "perfis.txt"

# ====== Formato de data ======
DATE_DISPLAY_FORMAT = "%d/%m/%Y"

def format_date_for_display(d):
    if pd.isna(d) or d is None:
        return ""
    if isinstance(d, str):
        try:
            d = pd.to_datetime(d).date()
        except Exception:
            return d
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(DATE_DISPLAY_FORMAT)

# ====== Config de alertas (persistente) ======
DEFAULT_CONFIG = {"valor_alerta": 2000.0, "dias_vencimento_alerta": 5}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        try:
            st.warning(f"Não foi possível salvar config: {e}")
        except Exception:
            pass

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

config = load_config()

# ====== Categorias e Perfis ======
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

CATEGORIAS_ENTRADA = load_categories_from_file(
    CATEGORIES_ENTRADA_FILE, ["Salário", "Outras Entradas"]
)
CATEGORIAS_GASTO = load_categories_from_file(
    CATEGORIES_GASTO_FILE,
    ["Aluguel", "Alimentação", "Combustível", "Água", "Luz", "Gás",
     "Condomínio", "Lazer", "Investimentos", "Outros Gastos"]
)
TODAS_CATEGORIAS = CATEGORIAS_ENTRADA + CATEGORIAS_GASTO

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

# ====== Cartões ======
def load_cards():
    if not os.path.exists(CARDS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Bandeira', 'Dono', 'DiaFechamento', 'DiaVencimento'])
        df.to_csv(CARDS_FILE, index=False)
        return df
    df = pd.read_csv(
        CARDS_FILE,
        dtype={'Nome': str, 'Bandeira': str, 'Dono': str,
               'DiaFechamento': 'Int64', 'DiaVencimento': 'Int64'}
    )
    return df

def save_cards(df_cards):
    df_cards.to_csv(CARDS_FILE, index=False)

# ====== Transações ======
def load_data(profile):
    try:
        df = pd.read_csv(f"{profile}_{DATA_FILE}")
        if not df.empty:
            # suporta datas em ISO ou já em datetime
            df['Data'] = pd.to_datetime(df['Data']).dt.date
        return df
    except FileNotFoundError:
        cols = ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor', 'PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas']
        return pd.DataFrame(columns=cols)

def save_data(df, profile):
    df_copy = df.copy()
    if 'Data' in df_copy.columns:
        df_copy['Data'] = pd.to_datetime(df_copy['Data']).dt.strftime('%Y-%m-%d')
    df_copy.to_csv(f"{profile}_{DATA_FILE}", index=False)

def add_transaction(df, data, tipo, categoria, descricao, valor, profile,
                    pago_com_cartao=False, cartao=None, num_parcelas=None, parcela_atual=None, gerar_parcelas=False):
    for col in ['PagoComCartao', 'Cartao', 'NumParcelas', 'ParcelaAtual', 'GerouParcelas']:
        if col not in df.columns:
            df[col] = pd.NA

    base = {
        'Data': pd.to_datetime(data).date() if not isinstance(data, date) else data,
        'Tipo': tipo,
        'Categoria': categoria,
        'Descrição': descricao,
        'Valor': float(valor),
        'PagoComCartao': 'Sim' if pago_com_cardao else 'Não' if False else ('Sim' if pago_com_cartao else 'Não'),
        'Cartao': cartao if pago_com_cartao else pd.NA,
        'NumParcelas': int(num_parcelas) if (pago_com_cartao and num_parcelas) else pd.NA,
        'ParcelaAtual': int(parcela_atual) if (pago_com_cartao and parcela_atual) else pd.NA,
        'GerouParcelas': 'Sim' if gerar_parcelas else 'Não'
    }
    # note: previous line had a small complexity; ensure PagoComCartao correct
    base['PagoComCartao'] = 'Sim' if pago_com_cartao else 'Não'

    new_rows = [base]

    if pago_com_cartao and gerar_parcelas and num_parcelas and int(num_parcelas) > 1:
        try:
            num = int(num_parcelas)
            start_parcela = int(parcela_atual) if parcela_atual else 1
            for p in range(start_parcela + 1, num + 1):
                new_date = pd.to_datetime(data).date() + relativedelta(months=(p - start_parcela))
                row = base.copy()
                row['Data'] = new_date
                row['ParcelaAtual'] = p
                row['Descrição'] = f"{descricao} ({p}/{num})"
                new_rows.append(row)
        except Exception as e:
            st.warning(f"Não foi possível gerar todas as parcelas automaticamente: {e}")

    df_new = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    save_data(df_new, profile)
    return df_new

# ====== Gráficos ======
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

# ====== Faturas ======
def add_months(dt, n):
    return (pd.to_datetime(dt) + relativedelta(months=n)).date()

def installments_from_row(row):
    installments = []
    try:
        paid_with_card = (str(row.get('PagoComCartao', 'Não')).lower() == 'sim')
        if not paid_with_card:
            return installments
    except Exception:
        return installments

    base_date = pd.to_datetime(row['Data']).date()
    valor_total = float(row['Valor']) if not pd.isna(row['Valor']) else 0.0
    num_parc = int(row['NumParcelas']) if (not pd.isna(row.get('NumParcelas'))) else 1
    parcela_atual = int(row['ParcelaAtual']) if (not pd.isna(row.get('ParcelaAtual'))) else 1
    gerou = str(row.get('GerouParcelas', 'Não')).lower() == 'sim'

    if gerou:
        installments.append({
            'Data': base_date,
            'Valor': valor_total,
            'Cartao': row.get('Cartao'),
            'Descrição': row.get('Descrição'),
            'ParcelaAtual': parcela_atual,
            'NumParcelas': num_parc
        })
    else:
        if num_parc > 1 and parcela_atual == 1:
            parcela_valor = round(valor_total / num_parc, 2)
            for p in range(1, num_parc + 1):
                dtp = add_months(base_date, p - 1)
                desc = f"{row.get('Descrição', '')} ({p}/{num_parc})" if row.get('Descrição') else f"Parcela {p}/{num_parc}"
                installments.append({
                    'Data': dtp,
                    'Valor': parcela_valor,
                    'Cartao': row.get('Cartao'),
                    'Descrição': desc,
                    'ParcelaAtual': p,
                    'NumParcelas': num_parc
                })
        else:
            installments.append({
                'Data': base_date,
                'Valor': valor_total,
                'Cartao': row.get('Cartao'),
                'Descrição': row.get('Descrição'),
                'ParcelaAtual': parcela_atual,
                'NumParcelas': num_parc
            })
    return installments

def billing_month_for_installment(install_date, card_closing_day):
    d = install_date
    if d.day <= card_closing_day:
        return d.year, d.month
    else:
        next_month = add_months(d, 1)
        return next_month.year, next_month.month

def get_card_invoices(profiles_list, months_ahead=12, start_year=None, start_month=None):
    cards_df = load_cards()
    # coletar todas as transações de todos os perfis
    all_rows = []
    for profile in profiles_list:
        dfp = load_data(profile)
        if dfp.empty:
            continue
        dfp = dfp.copy()
        dfp['Pessoa'] = profile
        all_rows.append(dfp)
    if not all_rows:
        return pd.DataFrame(columns=['Cartao', 'Dono', 'Year', 'Month', 'MonthKey', 'Valor', 'QtdeTransacoes', 'DiaVencimento']), {}

    df_all = pd.concat(all_rows, ignore_index=True)

    # gerar lista de parcelas previstas a partir das linhas
    installments = []
    for idx, row in df_all.iterrows():
        for inst in installments_from_row(row):
            inst_rec = inst.copy()
            inst_rec['Pessoa'] = row.get('Pessoa')
            inst_rec['OrigemIndex'] = idx
            installments.append(inst_rec)

    if len(installments) == 0:
        return pd.DataFrame(columns=['Cartao', 'Dono', 'Year', 'Month', 'MonthKey', 'Valor', 'QtdeTransacoes', 'DiaVencimento']), {}

    inst_df = pd.DataFrame(installments)
    inst_df['Data'] = pd.to_datetime(inst_df['Data']).dt.date

    # define start month
    today = date.today()
    if start_year and start_month:
        start = date(start_year, start_month, 1)
    else:
        start = date(today.year, today.month, 1)

    # build months window
    months = []
    for m in range(months_ahead):
        dt = add_months(start, m)
        months.append((dt.year, dt.month, dt.strftime("%Y-%m")))

    # for each installment, compute billing month based on card's day
    detail_map = {}  # (cartao, monthkey) -> list of installments
    records = []

    for _, inst in inst_df.iterrows():
        card_name = inst.get('Cartao')
        if pd.isna(card_name) or card_name is None:
            continue
        # find card closing day and owner
        card_row = cards_df[cards_df['Nome'] == card_name]
        if card_row.empty:
            closing_day = 31
            venc_day = 31
            owner = None
        else:
            closing_day = int(card_row.iloc[0].get('DiaFechamento', 31))
            venc_day = int(card_row.iloc[0].get('DiaVencimento', closing_day))
            owner = card_row.iloc[0]['Dono']
        inst_date = inst['Data']
        year_b, month_b = billing_month_for_installment(inst_date, closing_day)
        monthkey = f"{year_b:04d}-{month_b:02d}"

        # if monthkey is within our months window
        if any(mk == monthkey for (_, _, mk) in months):
            key = (card_name, monthkey)
            detail_map.setdefault(key, []).append({
                'Data': inst_date,
                'Valor': inst['Valor'],
                'Descrição': inst.get('Descrição'),
                'Pessoa': inst.get('Pessoa'),
                'ParcelaAtual': inst.get('ParcelaAtual'),
                'NumParcelas': inst.get('NumParcelas'),
                'DiaVencimento': venc_day
            })

    # aggregate records
    for card_name, monthkey in sorted({k for k in detail_map.keys()}, key=lambda x: (x[0], x[1])):
        parts = detail_map[(card_name, monthkey)]
        total = sum([p['Valor'] for p in parts])
        qtd = len(parts)
        # get owner
        card_row = cards_df[cards_df['Nome'] == card_name]
        owner = card_row.iloc[0]['Dono'] if not card_row.empty else None
        year, month = int(monthkey.split('-')[0]), int(monthkey.split('-')[1])
        # choose DiaVencimento (from parts first item)
        dia_venc = int(parts[0].get('DiaVencimento', 31)) if parts else 31
        records.append({
            'Cartao': card_name,
            'Dono': owner,
            'Year': year,
            'Month': month,
            'MonthKey': monthkey,
            'Valor': round(total, 2),
            'QtdeTransacoes': qtd,
            'DiaVencimento': dia_venc
        })

    df_records = pd.DataFrame(records)
    if df_records.empty:
        df_records = pd.DataFrame(columns=['Cartao', 'Dono', 'Year', 'Month', 'MonthKey', 'Valor', 'QtdeTransacoes', 'DiaVencimento'])
    else:
        df_records = df_records.sort_values(['Year', 'Month', 'Cartao'])

    return df_records, detail_map

# ====== UI ======
st.set_page_config(layout="wide", page_title="Gerenciamento de Custos Pessoais - Faturas")

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
        st.title("💳 Gerenciamento de Custos Pessoais (com Controle de Faturas)")

        profiles = load_profiles()
        cards_df = load_cards()

        tab_titles = ["Análise Geral"] + profiles + ["Gerenciamento de Perfis", "Gerenciamento de Categorias", "Gerenciamento de Cartões", "Controle de Faturas"]
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

        # colocar a aba de faturas no final (após cartões)
        st.markdown("---")
        st.header("📅 Controle de Faturas - Previsão por Cartão")

        # controles para faturas
        cards_df = load_cards()
        card_options = ['Todos'] + cards_df['Nome'].tolist() if not cards_df.empty else ['Todos']

        col1, col2, col3, col4 = st.columns([1,1,1,1])
        with col1:
            start_date = st.date_input("Mês inicial (usar 1º dia do mês)", value=date(date.today().year, date.today().month, 1))
        with col2:
            months_ahead = st.number_input("Meses à frente", min_value=1, max_value=24, value=12, step=1)
        with col3:
            selected_card = st.selectbox("Cartão (filtro)", card_options)
        with col4:
            valor_alerta = st.number_input("Valor para alerta de fatura alta (R$)", value=float(config.get('valor_alerta', 2000.0)), step=50.0)
            dias_alerta = st.number_input("Dias antes do vencimento para alerta", value=int(config.get('dias_vencimento_alerta', 5)), min_value=0, max_value=31, step=1)
            if st.button("Salvar configurações de alerta"):
                config['valor_alerta'] = float(valor_alerta)
                config['dias_vencimento_alerta'] = int(dias_alerta)
                save_config(config)
                st.success("Configurações salvas.")

        sy, sm = start_date.year, start_date.month
        df_invoices, detail_map = get_card_invoices(profiles, months_ahead=months_ahead, start_year=sy, start_month=sm)

        if selected_card != 'Todos':
            df_invoices = df_invoices[df_invoices['Cartao'] == selected_card]

        if df_invoices.empty:
            st.info("Nenhuma fatura prevista no período selecionado.")
        else:
            # calcular vencimento real e situação
            def get_month_last_day(year, month):
                return calendar.monthrange(year, month)[1]

            def compute_vencimento_and_status(row):
                year = int(row['Year']); month = int(row['Month'])
                dia_venc = int(row.get('DiaVencimento', row.get('DiaVencimento', 31)))
                last_day = get_month_last_day(year, month)
                dia_use = dia_venc if dia_venc <= last_day else last_day
                venc_date = date(year, month, dia_use)
                # status
                hoje = date.today()
                dias_para_vencer = (venc_date - hoje).days
                status = "🟢 OK"
                if dias_para_vencer < 0:
                    status = "⚪ Encerrada"
                elif dias_para_vencer <= dias_alerta:
                    status = "🔴 Vencimento Próximo"
                elif float(row['Valor']) > float(valor_alerta):
                    status = "🟠 Valor Alto"
                return venc_date, status

            df_display = df_invoices.copy()
            df_display['Mês Fatura'] = df_display['MonthKey'].apply(lambda x: datetime.strptime(x + "-01", "%Y-%m-%d").strftime("%b %Y"))
            if 'DiaVencimento' not in df_display.columns:
                df_display['DiaVencimento'] = df_display.get('DiaVencimento', 31)
            vencs = df_display.apply(compute_vencimento_and_status, axis=1)
            df_display['Vencimento Real'] = [format_date_for_display(v[0]) for v in vencs]
            df_display['Situação'] = [v[1] for v in vencs]
            df_display = df_display[['Cartao','Dono','Mês Fatura','Valor','QtdeTransacoes','Vencimento Real','Situação']]

            st.subheader("Resumo de Faturas")
            st.dataframe(df_display.reset_index(drop=True))

            st.subheader("Gráfico: Valor por Cartão por Mês")
            pivot = df_invoices.pivot_table(index='MonthKey', columns='Cartao', values='Valor', aggfunc='sum', fill_value=0)
            pivot = pivot.sort_index()
            fig = go.Figure()
            for col in pivot.columns:
                fig.add_trace(go.Bar(name=col, x=[datetime.strptime(k + "-01", "%Y-%m-%d").strftime("%b %Y") for k in pivot.index], y=pivot[col]))
            fig.update_layout(barmode='stack', xaxis_title="Mês da Fatura", yaxis_title="Valor (R$)", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.subheader("Detalhes por Fatura")
            keys = sorted(detail_map.keys(), key=lambda x: (x[0], x[1]))
            options = [f"{k[0]} — {k[1]}" for k in keys]
            if options:
                choice = st.selectbox("Selecionar fatura para ver transações", options)
                if choice:
                    chosen_card, chosen_monthkey = choice.split(" — ")
                    chosen_key = (chosen_card, chosen_monthkey)
                    details = detail_map.get(chosen_key, [])
                    if details:
                        det_df = pd.DataFrame(details)
                        det_df['Data'] = det_df['Data'].apply(lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"))
                        det_df = det_df[['Data','Descrição','Pessoa','ParcelaAtual','NumParcelas','Valor']]
                        st.dataframe(det_df.reset_index(drop=True))
                    else:
                        st.info("Nenhuma transação nesta fatura.")

    # --- Abas auxiliares ---
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

    def manage_cards_tab():
        st.header("💳 Gerenciamento de Cartões")

        cards_df = load_cards()
        st.subheader("Cartões Cadastrados")
        if cards_df.empty:
            st.info("Nenhum cartão cadastrado.")
        else:
            display_df = cards_df.copy()
            display_df['DiaFechamento'] = display_df['DiaFechamento'].astype('Int64')
            display_df['DiaVencimento'] = display_df['DiaVencimento'].astype('Int64')
            st.dataframe(display_df)

        st.markdown("---")
        st.subheader("Adicionar / Atualizar Cartão")
        with st.form("add_card_form"):
            nome = st.text_input("Nome do Cartão (ex: 'Nubank Visa')")
            bandeira = st.text_input("Bandeira (ex: Visa, MasterCard, Elo)")
            profiles = load_profiles()
            dono = st.selectbox("Dono do Cartão (perfil)", profiles)
            dia_fech = st.number_input("Dia de fechamento da fatura (1-31)", min_value=1, max_value=31, step=1)
            dia_venc = st.number_input("Dia de vencimento da fatura (1-31)", min_value=1, max_value=31, step=1, value=dia_fech)
            submitted_card = st.form_submit_button("Salvar Cartão")
            if submitted_card:
                if not nome:
                    st.warning("Insira o nome do cartão.")
                else:
                    if nome in cards_df['Nome'].values:
                        cards_df.loc[cards_df['Nome'] == nome, ['Bandeira', 'Dono', 'DiaFechamento', 'DiaVencimento']] = [bandeira, dono, int(dia_fech), int(dia_venc)]
                        save_cards(cards_df)
                        st.success("Cartão atualizado.")
                        st.rerun()
                    else:
                        new_row = pd.DataFrame([{'Nome': nome, 'Bandeira': bandeira, 'Dono': dono, 'DiaFechamento': int(dia_fech), 'DiaVencimento': int(dia_venc)}])
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

    def config_tab():
        st.header("⚙️ Configurações de Alertas")
        valor_alerta = st.number_input("Valor de alerta de fatura (R$)",
                                       min_value=100.0, step=50.0, value=config['valor_alerta'])
        dias_alerta = st.number_input("Dias antes do vencimento para alerta",
                                      min_value=1, step=1, value=config['dias_vencimento_alerta'])
        if st.button("Salvar configurações"):
            config['valor_alerta'] = valor_alerta
            config['dias_vencimento_alerta'] = dias_alerta
            save_config(config)
            st.success("Configurações salvas.")

if _name_ == "_main_":
    main()
