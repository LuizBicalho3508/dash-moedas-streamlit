import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time # Para mostrar a hora da atualização e adicionar pequenos delays

# --- Configuração da API ---
# Obtenha sua chave GRATUITA em https://www.exchangerate-api.com/
API_KEY = "f4d6dcbc983e407d21e061f8" # <-- SUBSTITUA PELA SUA CHAVE REAL
API_BASE_URL_LATEST = f"https://open.er-api.com/v6/latest/"
# Endpoint histórico para ExchangeRate-API é por data: /history/YYYY/MM/DD
API_BASE_URL_HISTORICAL = f"https://open.er-api.com/v6/history/"

# --- Funções para Obter Dados ---

# Função para buscar as taxas de câmbio mais recentes
# Cache os dados por 1 hora (3600 segundos) para não exceder o limite da API gratuita
@st.cache_data(ttl=3600)
def fetch_latest_rates(base_currency):
    """Fetches the latest exchange rates for a given base currency."""
    try:
        url = f"{API_BASE_URL_LATEST}{base_currency}?apikey={API_KEY}"
        response = requests.get(url)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if data and data.get("result") == "success":
            # Add a timestamp to show when the data was fetched
            data['timestamp'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            return data
        else:
            st.error(f"Erro na resposta da API ao buscar cotações recentes: {data.get('error', 'Erro desconhecido')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar na API para buscar cotações recentes: {e}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado ao processar cotações recentes: {e}")
        return None

# Função para buscar dados históricos dia a dia
# Cache os dados históricos por 24 horas (86400 segundos)
@st.cache_data(ttl=86400)
def fetch_historical_rates(base_currency, target_currencies, start_date, end_date):
    """Fetches historical exchange rates for a date range by querying day by day."""
    history_data = {}
    current_date = start_date
    date_list = []
    # Calculate the number of days in the range, limit to a reasonable number for free API
    total_days = (end_date - start_date).days + 1
    max_days_limit = 365 # Limit to one year of data to avoid excessive API calls

    st.write(f"Buscando dados históricos de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}...")

    # Use st.progress to show fetching progress
    progress_bar = st.progress(0)
    days_fetched = 0

    # Iterate through each day in the range
    while current_date <= end_date and days_fetched < max_days_limit:
        date_str = current_date.strftime("%Y/%m/%d")
        url = f"{API_BASE_URL_HISTORICAL}{date_str}/{base_currency}?apikey={API_KEY}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if data and data.get("result") == "success" and "rates" in data:
                date_list.append(current_date)
                for target in target_currencies:
                    if target in data["rates"]:
                        if target not in history_data:
                            history_data[target] = []
                        history_data[target].append(data["rates"][target])
                    else:
                         # Append None if currency data is missing for this date
                         if target not in history_data: history_data[target] = []
                         history_data[target].append(None)
            else:
                st.warning(f"Dados não disponíveis ou erro na API para a data {date_str}: {data.get('error', 'Erro desconhecido')}")
                # Append None for missing data points
                date_list.append(current_date)
                for target in target_currencies:
                    if target not in history_data: history_data[target] = []
                    history_data[target].append(None)


            current_date += timedelta(days=1)
            days_fetched += 1
            # Update progress bar
            progress_bar.progress(min(days_fetched / total_days, 1.0))
            time.sleep(0.05) # Small delay to be kind to the API

        except requests.exceptions.RequestException as e:
            st.warning(f"Erro ao buscar dados para {date_str}: {e}. Tentando próxima data...")
            current_date += timedelta(days=1)
            days_fetched += 1
            progress_bar.progress(min(days_fetched / total_days, 1.0))
            time.sleep(0.05)
        except Exception as e:
             st.warning(f"Erro inesperado ao processar dados para {date_str}: {e}. Tentando próxima data...")
             current_date += timedelta(days=1)
             days_fetched += 1
             progress_bar.progress(min(days_fetched / total_days, 1.0))
             time.sleep(0.05)


    progress_bar.empty() # Hide progress bar when done

    if not history_data or not date_list:
        st.error("Não foi possível carregar dados históricos para o período selecionado.")
        return pd.DataFrame()

    # Create DataFrame from fetched data
    df_history = pd.DataFrame(history_data, index=date_list)
    df_history.index.name = 'Data'
    df_history = df_history.reset_index() # Convert index to column for Plotly
    return df_history

# --- Função Principal do Dashboard ---

def main():
    # Configure page settings
    st.set_page_config(layout="wide", page_title="Monitoramento de Moedas", icon="💹")

    st.title("💹 Monitoramento de Cotações: Dólar e Outras Moedas")

    # --- Barra Lateral (Sidebar) ---
    st.sidebar.header("Configurações")

    # List of available currencies (can be expanded)
    available_currencies = ["USD", "BRL", "EUR", "JPY", "GBP", "CAD", "AUD", "ARS", "CLP", "CNY", "MXN", "CHF"]

    # Select base currency
    base_currency = st.sidebar.selectbox(
        "Moeda Base",
        available_currencies,
        index=available_currencies.index("USD") # Default to USD
    )

    # Select target currencies to compare
    # Filter out the base currency from target options
    target_currencies_options = [curr for curr in available_currencies if curr != base_currency]
    # Set default target currencies
    default_targets = ["BRL", "EUR"] if base_currency == "USD" else ["USD", "BRL"]
    # Ensure default targets are in the available options
    default_targets = [t for t in default_targets if t in target_currencies_options]

    target_currencies = st.sidebar.multiselect(
        "Selecionar Moedas para Comparar",
        target_currencies_options,
        default=default_targets
    )

    # Date range for historical data
    today = datetime.now().date()
    default_start_date = today - timedelta(days=180) # Default to last 6 months
    start_date = st.sidebar.date_input("Data Inicial (Histórico)", default_start_date)
    end_date = st.sidebar.date_input("Data Final (Histórico)", today)

    # Validate date range
    if start_date > end_date:
        st.sidebar.error("Erro: A data inicial não pode ser posterior à data final.")
        return # Stop execution if dates are invalid

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Dados fornecidos por [ExchangeRate-API](https://www.exchangerate-api.com/)")
    st.sidebar.markdown("Atualização das cotações recentes: a cada 1 hora.")
    st.sidebar.markdown("Atualização dos dados históricos: a cada 24 horas.")


    # --- Buscar e Apresentar Dados ---

    # Fetch latest data
    latest_data = fetch_latest_rates(base_currency)

    if latest_data:
        st.header("Cotações Atuais")

        last_updated = latest_data.get('timestamp', 'N/A')
        st.write(f"Última atualização dos dados da API: **{last_updated}**")

        # Create DataFrame for latest rates
        latest_rates_df = pd.DataFrame({
            'Moeda': list(latest_data['rates'].keys()),
            f'Taxa ({base_currency})': list(latest_data['rates'].values())
        })
        # Filter for selected currencies + base currency
        selected_latest_rates = latest_rates_df[latest_rates_df['Moeda'].isin(target_currencies + [base_currency])]

        # Display Latest Rates Table
        if not selected_latest_rates.empty:
             # Format the rate column for better readability
            selected_latest_rates[f'Taxa ({base_currency})'] = selected_latest_rates[f'Taxa ({base_currency})'].apply(lambda x: f'{x:,.4f}' if isinstance(x, (int, float)) else 'N/A')
            # Use st.columns for better layout
            col1, col2 = st.columns([1, 2])
            with col1:
                 st.subheader("Tabela de Cotações")
                 st.dataframe(selected_latest_rates.set_index('Moeda').T) # Transpose for better view

            # Bar Chart for Current Comparison (exclude base currency)
            with col2:
                st.subheader(f"Comparativo Atual (Base: {base_currency})")
                # Filter out the base currency for the bar chart comparison
                bar_chart_data = selected_latest_rates[selected_latest_rates['Moeda'] != base_currency].copy()
                # Ensure the rate column is numeric for plotting
                bar_chart_data[f'Taxa ({base_currency})'] = pd.to_numeric(bar_chart_data[f'Taxa ({base_currency})'], errors='coerce')
                bar_chart_data.dropna(subset=[f'Taxa ({base_currency})'], inplace=True)

                if not bar_chart_data.empty:
                    fig_bar = px.bar(
                        bar_chart_data,
                        x='Moeda',
                        y=f'Taxa ({base_currency})',
                        title=f'Cotações Atuais em relação a {base_currency}',
                        color='Moeda', # Different color for each bar
                        text=f'Taxa ({base_currency})' # Show value on top of bar
                    )
                    fig_bar.update_layout(yaxis_title=f"Taxa de Câmbio ({base_currency})")
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Selecione moedas para comparar para ver o gráfico de barras.")


    # Fetch and display Historical Data if target currencies are selected
    if target_currencies:
        historical_data = fetch_historical_rates(base_currency, target_currencies, start_date, end_date)

        if not historical_data.empty:
            st.header(f"Histórico de Cotações (Base: {base_currency})")

            # Melt the DataFrame for Plotly (long format is preferred)
            df_historical_melted = historical_data.melt(
                id_vars='Data',
                var_name='Moeda',
                value_name='Taxa de Câmbio'
            )
            # Remove rows with None values (dates where data was missing for a currency)
            df_historical_melted.dropna(subset=['Taxa de Câmbio'], inplace=True)

            if not df_historical_melted.empty:
                # Line Chart for Historical Evolution
                fig_line = px.line(
                    df_historical_melted,
                    x='Data',
                    y='Taxa de Câmbio',
                    color='Moeda', # A separate line for each currency
                    title=f'Evolução Histórica de {" vs ".join(target_currencies)} vs {base_currency}',
                    hover_data={"Data": "|%Y-%m-%d", "Taxa de Câmbio": ":.4f"} # Format hover tooltip
                )
                fig_line.update_layout(
                    xaxis_title="Data",
                    yaxis_title=f"Taxa de Câmbio ({base_currency})",
                    hovermode="x unified" # Show hover info for all lines at the same date
                )
                st.plotly_chart(fig_line, use_container_width=True)

                # Optional: Daily Percentage Change Chart
                st.subheader(f"Variação Percentual Diária (Base: {base_currency})")
                # Calculate daily percentage change for each currency
                # Set 'Data' as index first, then calculate pct_change
                df_pct_change = historical_data.set_index('Data')[target_currencies].pct_change() * 100
                # Stack to long format and reset index
                df_pct_change = df_pct_change.stack().reset_index(name='Variação %')
                df_pct_change.rename(columns={'level_1': 'Moeda'}, inplace=True)
                df_pct_change.dropna(inplace=True) # Remove the first day (no change) and any NaNs

                if not df_pct_change.empty:
                     fig_change = px.line(
                         df_pct_change,
                         x='Data',
                         y='Variação %',
                         color='Moeda',
                         title=f'Variação Percentual Diária vs {base_currency}',
                         hover_data={"Data": "|%Y-%m-%d", "Variação %": ":.2f%"}
                     )
                     fig_change.update_layout(
                         xaxis_title="Data",
                         yaxis_title="Variação Percentual (%)",
                         hovermode="x unified"
                     )
                     st.plotly_chart(fig_change, use_container_width=True)
                else:
                    st.info("Dados insuficientes para calcular a variação percentual diária.")

            else:
                st.info("Não há dados históricos disponíveis ou completos para o período e moedas selecionados.")

        else:
             st.info("Não foi possível carregar dados históricos. Verifique as configurações e a chave da API.")


    st.markdown("---")
    st.markdown("Dashboard criado com Streamlit, dados via ExchangeRate-API e gráficos com Plotly.")


# Run the Streamlit app
if __name__ == "__main__":
    main()
