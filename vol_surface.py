from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Any
import importlib.util
import sys

import numpy as np
import pandas as pd

try:
    from scipy.optimize import brentq
except Exception:
    brentq = None

SUPPORTED_ASSETS = {"Equity", "Index", "FX", "Commodity"}
SUPPORTED_OPTION_TYPES = {"Call", "Put"}
SUPPORTED_OPTION_STYLES = {"European", "American"}
SUPPORTED_AMERICAN_ENGINES = {"Trinomial"}


@dataclass
class VolSurfaceConfig:
    S: float
    Rd: float
    Rf: float = 0.0
    q: float = 0.0
    asset_type: str = "Equity"
    option_style: str = "European"
    american_engine: str = "Trinomial"
    valuation_date: str | pd.Timestamp = None
    default_option_type: str = "Call"
    pricing_module: Optional[Any] = None
    pricing_file: str = "pricing__2_.py"
    n_sim: int = 5000
    seed: Optional[int] = 42
    n_steps: int = 200
    poly_degree: int = 3
    div_dates: Optional[Any] = None
    div_amounts: Optional[Any] = None
    low_vol: float = 0.0001
    high_vol: float = 5.0
    tol: float = 1e-6
    max_iter: int = 100
    prefer_brentq: bool = True


def load_pricing_module(pricing_file: str | Path = "pricing__2_.py", alias: str = "pricing_src_for_vol_surface"):
    path = Path(pricing_file)
    if not path.is_absolute():
        path = Path(__file__).parent / path

    if not path.exists():
        raise FileNotFoundError(
            f"Не найден файл pricing-модуля: {path}. "
            f"Положи vol_surface.py рядом с pricing__2_.py или передай pricing_module явно."
        )

    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def normalize_option_type(option_type: str) -> str:
    value = str(option_type).strip().capitalize()
    if value not in SUPPORTED_OPTION_TYPES:
        raise ValueError(f"Option Type должен быть Call или Put, получено: {option_type!r}")
    return value


def normalize_option_style(option_style: str) -> str:
    value = str(option_style).strip().capitalize()
    aliases = {
        "eur": "European",
        "european": "European",
        "euro": "European",
        "us": "American",
        "usa": "American",
        "american": "American",
        "amer": "American",
    }
    value = aliases.get(value.lower(), value)
    if value not in SUPPORTED_OPTION_STYLES:
        raise ValueError(f"Option Style должен быть European или American, получено: {option_style!r}")
    return value


def normalize_american_engine(engine: str) -> str:
    value = str(engine).strip().lower()
    aliases = {
        "trinomial": "Trinomial",
        "trinomial tree": "Trinomial",
        "trinom": "Trinomial",
        "трехшаговое": "Trinomial",
        "триномиальное": "Trinomial",
        "триномиальное дерево": "Trinomial",
    }
    normalized = aliases.get(value, str(engine).strip())
    if normalized not in SUPPORTED_AMERICAN_ENGINES:
        raise ValueError("Для American options сейчас поддержан только engine='Trinomial'")
    return normalized


def normalize_asset_type(asset_type: str) -> str:
    value = str(asset_type).strip()
    aliases = {
        "equity": "Equity",
        "stock": "Equity",
        "index": "Index",
        "fx": "FX",
        "forex": "FX",
        "commodity": "Commodity",
    }
    value = aliases.get(value.lower(), value)
    if value not in SUPPORTED_ASSETS:
        raise ValueError(f"asset_type должен быть одним из {sorted(SUPPORTED_ASSETS)}, получено: {asset_type!r}")
    return value


def parse_date(value, field_name: str = "date") -> pd.Timestamp:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Поле {field_name!r} пустое")
    return pd.to_datetime(value, dayfirst=False, errors="raise").normalize()


def years_between(valuation_date, expiry_date) -> float:
    valuation = parse_date(valuation_date, "valuation_date")
    expiry = parse_date(expiry_date, "expiry_date")
    return float((expiry - valuation) / pd.Timedelta(days=365))


def _split_optional_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        return [x.strip() for x in text.split(",") if x.strip()]
    if isinstance(value, (list, tuple, pd.Series, np.ndarray)):
        return list(value)
    return [value]


def normalize_dividends(div_dates=None, div_amounts=None):

    dates_raw = _split_optional_list(div_dates)
    amounts_raw = _split_optional_list(div_amounts)

    if not dates_raw and not amounts_raw:
        return [], []
    if len(dates_raw) != len(amounts_raw):
        raise ValueError("Число дат дивидендов и сумм дивидендов должно совпадать")

    dates = [parse_date(d, "Dividend Date") for d in dates_raw]
    amounts = [float(str(a).replace(",", ".")) for a in amounts_raw]
    return dates, amounts


def implied_vol_bisection(
    market_price: float,
    price_func: Callable[[float], float],
    low: float = 0.0001,
    high: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float:

    market_price = float(market_price)
    low = float(low)
    high = float(high)

    if market_price <= 0:
        raise ValueError("Market Price должен быть > 0")
    if low <= 0 or high <= 0 or low >= high:
        raise ValueError("Границы волатильности должны удовлетворять 0 < low < high")

    f_low = float(price_func(low)) - market_price
    f_high = float(price_func(high)) - market_price

    if not np.isfinite(f_low) or not np.isfinite(f_high):
        raise ValueError("Модель вернула NaN/inf на границах поиска volatility")

    if abs(f_low) <= tol:
        return low
    if abs(f_high) <= tol:
        return high

    if f_low * f_high > 0:
        low_price = f_low + market_price
        high_price = f_high + market_price
        raise ValueError(
            "Market Price не попадает в диапазон модельных цен на заданном интервале volatility: "
            f"price({low:.6f})={low_price:.8f}, price({high:.6f})={high_price:.8f}, "
            f"market={market_price:.8f}. Увеличь high_vol или проверь цену."
        )

    left, right = low, high
    for _ in range(max_iter):
        mid = 0.5 * (left + right)
        f_mid = float(price_func(mid)) - market_price

        if abs(f_mid) <= tol or (right - left) <= tol:
            return mid

        if f_low * f_mid <= 0:
            right = mid
            f_high = f_mid
        else:
            left = mid
            f_low = f_mid

    return 0.5 * (left + right)


def implied_vol(
    market_price: float,
    price_func: Callable[[float], float],
    low: float = 0.0001,
    high: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
    prefer_brentq: bool = True,
) -> float:

    if prefer_brentq and brentq is not None:
        def objective(sig: float) -> float:
            return float(price_func(sig)) - float(market_price)

        f_low = objective(low)
        f_high = objective(high)
        if abs(f_low) <= tol:
            return low
        if abs(f_high) <= tol:
            return high
        if f_low * f_high > 0:
            return implied_vol_bisection(market_price, price_func, low, high, tol, max_iter)
        return float(brentq(objective, low, high, xtol=tol, maxiter=max_iter))

    return implied_vol_bisection(market_price, price_func, low, high, tol, max_iter)


def select_european_option_class(pricing_module, asset_type: str):
    asset_type = normalize_asset_type(asset_type)
    if asset_type == "Equity":
        return pricing_module.EUR_S_EQ_option
    if asset_type == "Index":
        return getattr(pricing_module, "EUR_S_IND_option", pricing_module.EUR_S_EQ_option)
    if asset_type == "FX":
        return pricing_module.EUR_F_FX_option
    if asset_type == "Commodity":
        return getattr(pricing_module, "EUR_F_Commodity_option", pricing_module.EUR_F_FX_option)
    raise ValueError(f"Неподдерживаемый asset_type: {asset_type}")


def select_american_option_class(pricing_module, asset_type: str):
    asset_type = normalize_asset_type(asset_type)
    if asset_type not in ("Equity", "Index"):
        raise ValueError("American options сейчас поддержаны только для Equity/Index")
    if not hasattr(pricing_module, "US_S_EQ_option"):
        raise ValueError("В pricing__2_.py не найден класс US_S_EQ_option")
    return pricing_module.US_S_EQ_option


def make_price_func(
    *,
    pricing_module,
    asset_type: str,
    S: float,
    K: float,
    T: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    option_type: str = "Call",
    option_style: str = "European",
    american_engine: str = "Trinomial",
    n_sim: int = 5000,
    seed: Optional[int] = 42,
    n_steps: int = 200,
    poly_degree: int = 3,
    div_dates=None,
    div_amounts=None,
    valuation_date=None,
) -> Callable[[float], float]:

    asset_type = normalize_asset_type(asset_type)
    option_type = normalize_option_type(option_type)
    option_style = normalize_option_style(option_style)

    if option_style == "European":
        option_class = select_european_option_class(pricing_module, asset_type)

        def price_func(sigma: float) -> float:
            sigma = max(float(sigma), 1e-12)
            if asset_type in ("FX", "Commodity"):
                opt = option_class(
                    S=float(S), K=float(K), T=float(T), Rd=float(Rd), Rf=float(Rf),
                    Sig=sigma, q=float(q), Option_type=option_type, N_sim=int(n_sim), seed=seed
                )
            else:
                opt = option_class(
                    S=float(S), K=float(K), T=float(T), Rd=float(Rd),
                    Sig=sigma, q=float(q), Option_type=option_type, N_sim=int(n_sim), seed=seed
                )

            if option_type == "Call":
                return float(opt.Call_price())
            return float(opt.Put_price())

        return price_func


    american_engine = normalize_american_engine(american_engine)

    def price_func(sigma: float) -> float:


        sigma = max(float(sigma), 0.02)
        return trinomial_tree_price(
            asset_type=asset_type,
            option_style="American",
            S=float(S),
            K=float(K),
            T=float(T),
            Rd=float(Rd),
            Rf=float(Rf),
            q=float(q),
            sigma=sigma,
            option_type=option_type,
            n_steps=int(n_steps),
        )

    return price_func


def model_price(
    *, pricing_module, asset_type: str, S: float, K: float, T: float, Rd: float,
    Rf: float = 0.0, q: float = 0.0, sigma: float, option_type: str = "Call",
    option_style: str = "European", american_engine: str = "Trinomial",
    n_sim: int = 5000, seed: Optional[int] = 42,
    n_steps: int = 200, poly_degree: int = 3,
    div_dates=None, div_amounts=None, valuation_date=None,
) -> float:
    return make_price_func(
        pricing_module=pricing_module, asset_type=asset_type, S=S, K=K, T=T,
        Rd=Rd, Rf=Rf, q=q, option_type=option_type, option_style=option_style,
        american_engine=american_engine, n_sim=n_sim, seed=seed, n_steps=n_steps,
        poly_degree=poly_degree, div_dates=div_dates, div_amounts=div_amounts,
        valuation_date=valuation_date,
    )(sigma)


def calculate_greeks(
    *,
    pricing_module,
    asset_type: str,
    S: float,
    K: float,
    T: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    sigma: float,
    option_type: str = "Call",
    option_style: str = "European",
    american_engine: str = "Trinomial",
    n_sim: int = 5000,
    seed: Optional[int] = 42,
    n_steps: int = 200,
    poly_degree: int = 3,
    div_dates=None,
    div_amounts=None,
    valuation_date=None,
    h_s: Optional[float] = None,
    h_vol: float = 0.0001,
    h_t: float = 1 / 365,
    h_r: float = 0.0001,
) -> dict[str, float]:

    asset_type = normalize_asset_type(asset_type)
    option_type = normalize_option_type(option_type)
    option_style = normalize_option_style(option_style)
    if option_style == "American":
        american_engine = normalize_american_engine(american_engine)

    S = float(S)
    K = float(K)
    T = float(T)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    sigma = float(sigma)

    if not np.isfinite(sigma) or sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return {"Delta": np.nan, "Gamma": np.nan, "Vega": np.nan, "Theta": np.nan, "Rho": np.nan}

    if h_s is None:
        h_s = max(abs(S) * 0.001, 0.01)

    def p(S_=S, T_=T, Rd_=Rd, sigma_=sigma):
        if T_ <= 0 or S_ <= 0 or sigma_ <= 0:
            return np.nan
        return model_price(
            pricing_module=pricing_module,
            asset_type=asset_type,
            S=S_, K=K, T=T_, Rd=Rd_, Rf=Rf, q=q,
            sigma=sigma_, option_type=option_type,
            option_style=option_style,
            american_engine=american_engine,
            n_sim=n_sim, seed=seed,
            n_steps=n_steps, poly_degree=poly_degree,
            div_dates=div_dates, div_amounts=div_amounts,
            valuation_date=valuation_date,
        )

    base = p()
    s_down = max(S - h_s, 1e-8)
    up = p(S_=S + h_s)
    down = p(S_=s_down)

    delta = (up - down) / ((S + h_s) - s_down) if np.isfinite(up) and np.isfinite(down) else np.nan
    gamma = (up - 2 * base + down) / (h_s ** 2) if np.isfinite(up) and np.isfinite(base) and np.isfinite(down) else np.nan

    v_up = p(sigma_=sigma + h_vol)
    vega = (v_up - base) / h_vol if np.isfinite(v_up) and np.isfinite(base) else np.nan

    if T > h_t:
        t_down = p(T_=T - h_t)
        theta = (t_down - base) / h_t if np.isfinite(t_down) and np.isfinite(base) else np.nan
    else:
        theta = np.nan

    r_up = p(Rd_=Rd + h_r)
    rho = (r_up - base) / h_r if np.isfinite(r_up) and np.isfinite(base) else np.nan

    return {
        "Delta": float(delta) if np.isfinite(delta) else np.nan,
        "Gamma": float(gamma) if np.isfinite(gamma) else np.nan,
        "Vega": float(vega) if np.isfinite(vega) else np.nan,
        "Theta": float(theta) if np.isfinite(theta) else np.nan,
        "Rho": float(rho) if np.isfinite(rho) else np.nan,
    }


def trinomial_tree_price(
    *,
    asset_type: str,
    option_style: str,
    S: float,
    K: float,
    T: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    sigma: float,
    option_type: str = "Call",
    n_steps: int = 200,
) -> float:

    asset_type = normalize_asset_type(asset_type)
    option_type = normalize_option_type(option_type)
    option_style = normalize_option_style(option_style)

    S = float(S)
    K = float(K)
    T = float(T)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    sigma = float(sigma)
    n_steps = int(n_steps)

    if S <= 0 or K <= 0:
        raise ValueError("S и K должны быть > 0")
    if T <= 0:
        raise ValueError("T должен быть > 0")
    if sigma <= 0:
        raise ValueError("sigma должна быть > 0")
    if n_steps <= 0:
        raise ValueError("n_steps должен быть > 0")

    dt = T / n_steps
    disc = np.exp(-Rd * dt)

    if asset_type in ("Equity", "Index"):
        drift = Rd - q
    elif asset_type in ("FX", "Commodity"):
        drift = Rd - Rf
    else:
        drift = Rd

    sig = max(sigma, 1e-8)
    u = np.exp(sig * np.sqrt(3.0 * dt))
    nu = drift - 0.5 * sig * sig
    lam = (nu * np.sqrt(dt)) / (2.0 * sig * np.sqrt(3.0))

    pu = 1.0 / 6.0 + lam
    pdn = 1.0 / 6.0 - lam
    pm = 1.0 - pu - pdn

    pu = max(0.0, min(1.0, pu))
    pdn = max(0.0, min(1.0, pdn))
    pm = max(0.0, min(1.0, pm))
    total = pu + pm + pdn
    if total <= 0:
        raise ValueError("Некорректные вероятности триномиального дерева")
    pu, pm, pdn = pu / total, pm / total, pdn / total

    j_values = np.arange(-n_steps, n_steps + 1)
    ST = S * (u ** j_values)
    if option_type == "Call":
        values = np.maximum(ST - K, 0.0)
    else:
        values = np.maximum(K - ST, 0.0)

    is_american = option_style == "American"

    for step in range(n_steps - 1, -1, -1):
        continuation = disc * (
            pdn * values[0: 2 * step + 1]
            + pm * values[1: 2 * step + 2]
            + pu * values[2: 2 * step + 3]
        )

        if is_american:
            j_now = np.arange(-step, step + 1)
            S_now = S * (u ** j_now)
            if option_type == "Call":
                exercise = np.maximum(S_now - K, 0.0)
            else:
                exercise = np.maximum(K - S_now, 0.0)
            values = np.maximum(continuation, exercise)
        else:
            values = continuation

    return float(values[0])


def calc_option_greeks_trinomial(
    *,
    asset_type: str,
    option_style: str,
    S: float,
    K: float,
    T: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    sigma: float,
    option_type: str = "Call",
    n_steps: int = 200,
    h_s: Optional[float] = None,
    h_vol: float = 0.0001,
    h_t: float = 1 / 365,
    h_r: float = 0.0001,
) -> dict[str, float]:

    S = float(S)
    K = float(K)
    T = float(T)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    sigma = float(sigma)
    n_steps = int(n_steps)

    if h_s is None:
        h_s = max(abs(S) * 0.001, 0.01)

    def price(S_=S, T_=T, Rd_=Rd, sigma_=sigma):
        if S_ <= 0 or T_ <= 0 or sigma_ <= 0:
            return np.nan
        return trinomial_tree_price(
            asset_type=asset_type,
            option_style=option_style,
            S=S_,
            K=K,
            T=T_,
            Rd=Rd_,
            Rf=Rf,
            q=q,
            sigma=sigma_,
            option_type=option_type,
            n_steps=n_steps,
        )

    base = price()
    s_down = max(S - h_s, 1e-8)
    p_up = price(S_=S + h_s)
    p_down = price(S_=s_down)

    delta = (p_up - p_down) / ((S + h_s) - s_down) if np.isfinite(p_up) and np.isfinite(p_down) else np.nan
    gamma = (p_up - 2.0 * base + p_down) / (h_s ** 2) if np.isfinite(p_up) and np.isfinite(base) and np.isfinite(p_down) else np.nan

    p_vol_up = price(sigma_=sigma + h_vol)
    vega = (p_vol_up - base) / h_vol if np.isfinite(p_vol_up) and np.isfinite(base) else np.nan

    if T > h_t:
        p_t_down = price(T_=T - h_t)
        theta = (p_t_down - base) / h_t if np.isfinite(p_t_down) and np.isfinite(base) else np.nan
    else:
        theta = np.nan

    p_r_up = price(Rd_=Rd + h_r)
    rho = (p_r_up - base) / h_r if np.isfinite(p_r_up) and np.isfinite(base) else np.nan

    return {
        "Price": float(base) if np.isfinite(base) else np.nan,
        "Delta": float(delta) if np.isfinite(delta) else np.nan,
        "Gamma": float(gamma) if np.isfinite(gamma) else np.nan,
        "Vega": float(vega) if np.isfinite(vega) else np.nan,
        "Theta": float(theta) if np.isfinite(theta) else np.nan,
        "Rho": float(rho) if np.isfinite(rho) else np.nan,
    }


def _standardize_market_data_columns(market_data: pd.DataFrame) -> pd.DataFrame:

    df = market_data.copy()
    rename_map = {}
    normalized = {str(c).strip().lower().replace("_", " "): c for c in df.columns}

    aliases = {
        "Ticker": ["ticker", "symbol", "secid", "instrument", "тикер"],
        "Strike": ["strike", "k", "страйк"],
        "Expiry Date": ["expiry date", "expiry", "expiration", "maturity", "date", "дата экспирации"],
        "Market Price": ["market price", "price", "option price", "market", "рыночная цена"],
        "Option Type": ["option type", "type", "call put", "call/put", "тип опциона"],
    }

    for target, names in aliases.items():
        for name in names:
            if name in normalized:
                rename_map[normalized[name]] = target
                break

    df = df.rename(columns=rename_map)
    required = ["Strike", "Expiry Date", "Market Price"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            "В market_data не хватает обязательных колонок: "
            f"{missing}. Нужны Strike, Expiry Date, Market Price, Option Type(optional), Ticker(optional)."
        )

    return df


def calculate_vol_surface(
    market_data: pd.DataFrame,
    *,
    S: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    asset_type: str = "Equity",
    option_style: str = "European",
    american_engine: str = "Trinomial",
    valuation_date: str | pd.Timestamp = None,
    default_option_type: str = "Call",
    pricing_module=None,
    pricing_file: str = "pricing__2_.py",
    n_sim: int = 5000,
    seed: Optional[int] = 42,
    n_steps: int = 200,
    poly_degree: int = 3,
    div_dates=None,
    div_amounts=None,
    low_vol: float = 0.0001,
    high_vol: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
    prefer_brentq: bool = True,
    price_diff_warning_pct: float = 15.0,
) -> pd.DataFrame:

    if valuation_date is None:
        valuation_date = pd.Timestamp.today().normalize()

    pricing_module = pricing_module or load_pricing_module(pricing_file)
    asset_type = normalize_asset_type(asset_type)
    option_style = normalize_option_style(option_style)
    american_engine = normalize_american_engine(american_engine) if option_style == "American" else ""
    default_option_type = normalize_option_type(default_option_type)


    div_dates_norm, div_amounts_norm = normalize_dividends(div_dates, div_amounts)

    df = _standardize_market_data_columns(market_data)
    rows = []

    for _, row in df.iterrows():
        out = {
            "Ticker": "",
            "Strike": np.nan,
            "Expiry Date": None,
            "T": np.nan,
            "Market Price": np.nan,
            "Option Type": default_option_type,
            "Option Style": option_style,
            "Engine": american_engine if option_style == "American" else "Analytical",
            "Implied Vol": np.nan,
            "Model Price": np.nan,
            "Error": np.nan,
            "Delta": np.nan,
            "Gamma": np.nan,
            "Vega": np.nan,
            "Theta": np.nan,
            "Rho": np.nan,
            "Status": "",
        }

        try:
            ticker = ""
            if "Ticker" in df.columns and pd.notna(row.get("Ticker")):
                ticker = str(row.get("Ticker", "")).strip()
            K = float(str(row["Strike"]).replace(",", "."))
            expiry = parse_date(row["Expiry Date"], "Expiry Date")
            market_price = float(str(row["Market Price"]).replace(",", "."))
            option_type = normalize_option_type(row.get("Option Type", default_option_type))
            T = years_between(valuation_date, expiry)

            out.update({
                "Ticker": ticker,
                "Strike": K,
                "Expiry Date": expiry.strftime("%Y-%m-%d"),
                "T": T,
                "Market Price": market_price,
                "Option Type": option_type,
            })

            if K <= 0:
                raise ValueError("Strike должен быть > 0")
            if T <= 0:
                raise ValueError("Expiry Date должна быть позже Valuation Date")
            if market_price <= 0:
                raise ValueError("Market Price должен быть > 0")

            price_func = make_price_func(
                pricing_module=pricing_module,
                asset_type=asset_type,
                S=S,
                K=K,
                T=T,
                Rd=Rd,
                Rf=Rf,
                q=q,
                option_type=option_type,
                option_style=option_style,
                american_engine=american_engine if option_style == "American" else "Trinomial",
                n_sim=n_sim,
                seed=seed,
                n_steps=n_steps,
                poly_degree=poly_degree,
                div_dates=div_dates_norm,
                div_amounts=div_amounts_norm,
                valuation_date=valuation_date,
            )

            effective_low_vol = max(float(low_vol), 0.02) if option_style == "American" else float(low_vol)
            sigma = implied_vol(
                market_price=market_price,
                price_func=price_func,
                low=effective_low_vol,
                high=high_vol,
                tol=tol,
                max_iter=max_iter,
                prefer_brentq=prefer_brentq,
            )
            model_p = float(price_func(sigma))
            error = model_p - market_price
            price_diff_pct = abs(error) / abs(market_price) * 100.0 if market_price != 0 else np.nan

            greeks = calculate_greeks(
                pricing_module=pricing_module,
                asset_type=asset_type,
                S=S,
                K=K,
                T=T,
                Rd=Rd,
                Rf=Rf,
                q=q,
                sigma=sigma,
                option_type=option_type,
                option_style=option_style,
                american_engine=american_engine if option_style == "American" else "Trinomial",
                n_sim=n_sim,
                seed=seed,
                n_steps=n_steps,
                poly_degree=poly_degree,
                div_dates=div_dates_norm,
                div_amounts=div_amounts_norm,
                valuation_date=valuation_date,
            )

            status = "OK"
            if np.isfinite(price_diff_pct) and price_diff_pct > price_diff_warning_pct:
                status = f"WARNING: Model Price отличается от Market Price более чем на {price_diff_warning_pct:g}%"

            out.update({
                "Implied Vol": sigma,
                "Model Price": model_p,
                "Error": error,
                **greeks,
                "Status": status,
            })

        except Exception as exc:
            out["Status"] = f"ERROR: {exc}"

        rows.append(out)

    result = pd.DataFrame(rows)


    if not result.empty:
        key_cols = ["Strike", "Expiry Date", "Option Type"]
        valid = result["Market Price"].notna() & result["Strike"].notna() & result["Expiry Date"].notna()
        rounded_prices = result.loc[valid, "Market Price"].astype(float).round(10)
        tmp = result.loc[valid, key_cols].copy()
        tmp["_rounded_market_price"] = rounded_prices.values
        conflict_keys = set()
        for key, group in tmp.groupby(key_cols, dropna=False):
            if group["_rounded_market_price"].nunique(dropna=True) > 1:
                conflict_keys.add(key)

        if conflict_keys:
            for i, row in result.iterrows():
                key = (row.get("Strike"), row.get("Expiry Date"), row.get("Option Type"))
                status = str(row.get("Status", ""))
                if key in conflict_keys and status == "OK":
                    result.at[i, "Status"] = (
                        "WARNING: одинаковые Strike + Expiry Date + Option Type, "
                        "но разные Market Price"
                    )

    return result


def demo_sigma(strike: float, T: float, S: float) -> float:

    moneyness = float(strike) / float(S) - 1.0
    return 0.22 + 0.055 * abs(moneyness) + 0.020 * max(float(T), 0.0)


def generate_demo_market_data(
    *,
    pricing_module,
    asset_type: str = "Equity",
    option_style: str = "European",
    american_engine: str = "Trinomial",
    S: float = 62.16,
    Rd: float = 0.0425,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date: str | pd.Timestamp = None,
    strikes: Optional[list[float]] = None,
    expiry_day_offsets: Optional[list[int]] = None,
    n_sim: int = 5000,
    seed: Optional[int] = 42,
    n_steps: int = 200,
    poly_degree: int = 3,
    div_dates=None,
    div_amounts=None,
) -> pd.DataFrame:

    if valuation_date is None:
        valuation_date = pd.Timestamp.today().normalize()
    valuation_date = parse_date(valuation_date, "valuation_date")
    asset_type = normalize_asset_type(asset_type)
    option_style = normalize_option_style(option_style)
    american_engine = normalize_american_engine(american_engine) if option_style == "American" else "Trinomial"
    S = float(S)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)


    if strikes is None:
        strikes = [50, 55, 60, 65, 70, 75]
    if expiry_day_offsets is None:
        expiry_day_offsets = [90, 180, 270, 365]

    div_dates_norm, div_amounts_norm = normalize_dividends(div_dates, div_amounts)

    rows = []
    for offset in expiry_day_offsets:
        expiry = (valuation_date + pd.Timedelta(days=int(offset))).strftime("%Y-%m-%d")
        T = years_between(valuation_date, expiry)
        for strike in strikes:
            K = float(strike)
            sigma = demo_sigma(K, T, S)
            for option_type in ("Call", "Put"):
                market_price = model_price(
                    pricing_module=pricing_module,
                    asset_type=asset_type,
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Rf=Rf,
                    q=q,
                    sigma=sigma,
                    option_type=option_type,
                    option_style=option_style,
                    american_engine=american_engine,
                    n_sim=n_sim,
                    seed=seed,
                    n_steps=n_steps,
                    poly_degree=poly_degree,
                    div_dates=div_dates_norm,
                    div_amounts=div_amounts_norm,
                    valuation_date=valuation_date,
                )
                style_short = "A" if option_style == "American" else "E"
                rows.append({
                    "Ticker": f"D-{style_short}-{option_type[0]}-{expiry.replace('-', '')}-{int(K) if K.is_integer() else K}",
                    "Strike": K,
                    "Expiry Date": expiry,
                    "Market Price": round(float(market_price), 6),
                    "Option Type": option_type,
                })

    return pd.DataFrame(rows, columns=["Ticker", "Strike", "Expiry Date", "Market Price", "Option Type"])


def load_market_data(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    raise ValueError("Поддерживаются только CSV, XLSX и XLS файлы")


def save_result(result: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        result.to_csv(path, index=False)
    elif suffix in (".xlsx", ".xls"):
        result.to_excel(path, index=False)
    else:
        raise ValueError("Поддерживаются только CSV, XLSX и XLS файлы")


if __name__ == "__main__":
    pricing = load_pricing_module()
    valuation_date = "2026-06-15"
    S = 62.16
    Rd = 0.0425
    q = 0.0
    demo = generate_demo_market_data(
        pricing_module=pricing,
        asset_type="Equity",
        option_style="American",
        S=S,
        Rd=Rd,
        q=q,
        valuation_date=valuation_date,
        n_steps=75,
    )
    res = calculate_vol_surface(
        market_data=demo.head(8),
        S=S,
        Rd=Rd,
        q=q,
        asset_type="Equity",
        option_style="American",
        american_engine="Trinomial",
        valuation_date=valuation_date,
        pricing_module=pricing,
        n_steps=75,
    )
    print(res.to_string(index=False))
