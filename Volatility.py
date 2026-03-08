# volatility.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf

# ----------------- Загрузка CSV -----------------
def load_csv_data(path):
    """
    Загружает CSV с форматом:
    <TICKER>;<PER>;<DATE>;<TIME>;<OPEN>;<HIGH>;<LOW>;<CLOSE>;<VOL>
    """
    cols = ["TICKER", "PER", "DATE", "TIME", "Open", "High", "Low", "Close", "Volume"]
    
    # Загружаем все как строки
    df = pd.read_csv(path, sep=";", names=cols, header=0, dtype=str)
    
    # Убираем пробелы
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    
    # Конвертируем числовые колонки
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
    
    # Volume тоже конвертируем
    df["Volume"] = df["Volume"].str.replace(",", "").astype(float).astype(int)
    
    # Объединяем дату и время в datetime
    df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], dayfirst=True, errors="coerce")
    df.set_index("DATETIME", inplace=True)
    
    # Оставляем только нужные колонки для графиков
    return df[["Open", "High", "Low", "Close", "Volume"]]


# ----------------- Вычисление волатильностей -----------------
def calculate_historical_volatility(df, window=20):
    """
    Рассчитывает историческую волатильность по закрытию.
    """
    returns = df["Close"].pct_change().dropna()
    vol = returns.rolling(window=window).std() * np.sqrt(252)  # annualized
    return vol


def calculate_log_volatility(df, window=20):
    """
    Рассчитывает волатильность по логарифмическим доходностям.
    """
    log_returns = np.log(df["Close"] / df["Close"].shift(1)).dropna()
    vol = log_returns.rolling(window=window).std() * np.sqrt(252)  # annualized
    return vol


def calculate_rolling_volatility(df, window=20):
    """
    Скользящая волатильность по процентным изменениям.
    """
    returns = df["Close"].pct_change().dropna()
    rolling_vol = returns.rolling(window=window).std() * np.sqrt(252)
    return rolling_vol


def calculate_all_volatilities(df, window=20):
    """
    Возвращает словарь со всеми волатильностями.
    """
    return {
        "historical": calculate_historical_volatility(df, window),
        "log": calculate_log_volatility(df, window),
        "rolling": calculate_rolling_volatility(df, window)
    }


# ----------------- Выравнивание волатильности -----------------
def align_volatility(df, vol_series):
    """
    Выравнивает серию волатильности по длине df, добавляя NaN в начало.
    """
    vol_aligned = pd.Series(index=df.index, dtype=float)
    vol_aligned.iloc[-len(vol_series):] = vol_series.values
    return vol_aligned


# ----------------- Построение графиков -----------------
def plot_candlestick(df, title="Candlestick Chart", mav=(5, 20)):
    """
    Рисует свечной график с объемом.
    """
    mpf.plot(
        df,
        type="candle",
        volume=True,
        title=title,
        style="yahoo",
        mav=mav
    )


def plot_candlestick_with_volatility(df, volatility_series=None, title="Candlestick + Volatility"):
    """
    Рисует свечной график с объемом и оранжевой линией волатильности.
    """
    df_plot = df.copy()
    df_plot.index = pd.to_datetime(df_plot.index)
    df_plot = df_plot[['Open', 'High', 'Low', 'Close', 'Volume']]

    addplots = []
    if volatility_series is not None:
        vol_aligned = align_volatility(df_plot, volatility_series)
        addplots.append(mpf.make_addplot(vol_aligned, color='orange', panel=0, ylabel='Volatility'))

    mpf.plot(
        df_plot,
        type='candle',
        style='yahoo',
        volume=True,
        title=title,
        addplot=addplots,
        mav=(5,20),
        tight_layout=True
    )

def export_all_data(df, vols_dict, filepath):
    """
    Сохраняет CSV с Open, High, Low, Close, Volume + все волатильности
    """
    df_export = df.copy()
    for k,v in vols_dict.items():
        df_export[k + "Vol"] = align_volatility(df_export, v)
    df_export.to_csv(filepath)
