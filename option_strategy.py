from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import json
import importlib.util
import sys

import numpy as np
import pandas as pd


STRATEGY_COLUMNS = [
    "Instrument", "Side", "Option Type", "Quantity", "Strike", "Expiry Date",
    "Premium", "Sigma", "Style", "Asset Type",
]

LEG_RESULT_COLUMNS = [
    "Instrument", "Side", "Option Type", "Quantity", "Strike", "Expiry Date",
    "Premium", "Sigma", "Style", "Asset Type", "T", "Model Price", "Leg Value",
    "Delta", "Gamma", "Vega", "Theta", "Rho", "Status",
]

SUPPORTED_INSTRUMENTS = {"Option", "Future", "Spot"}
SUPPORTED_SIDES = {"Buy", "Sell"}
SUPPORTED_OPTION_TYPES = {"Call", "Put"}
SUPPORTED_STYLES = {"European", "American"}
SUPPORTED_ASSETS = {"Equity", "Index", "FX", "Commodity"}


RISK_MATRIX_SCENARIO_FACTORS = ["S", "Volatility", "Rd", "Rf", "q", "Delta", "Gamma", "Vega", "Theta", "Rho"]
RISK_MATRIX_VALUE_METRICS = ["Total P/L Today", "P/L at Expiry", "Strategy Price"]

RISK_MATRIX_METRICS = RISK_MATRIX_VALUE_METRICS


def _load_module(filename: str | Path, alias: str):
    path = Path(filename)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл модуля: {path}")
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def load_pricing_module(pricing_file: str | Path = "pricing__2_.py"):
    return _load_module(pricing_file, "pricing_src_for_option_strategy")


def load_vol_surface_module(vol_surface_file: str | Path = "vol_surface.py"):
    return _load_module(vol_surface_file, "vol_surface_src_for_option_strategy")


def _clean_str(value, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    text = str(value).strip()
    return text if text else default


def _to_float(value, default: Optional[float] = None, field_name: str = "value") -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        if default is not None:
            return float(default)
        raise ValueError(f"Поле {field_name!r} пустое")
    text = str(value).strip().replace(",", ".")
    if text == "":
        if default is not None:
            return float(default)
        raise ValueError(f"Поле {field_name!r} пустое")
    return float(text)


def parse_date(value, field_name: str = "date") -> pd.Timestamp:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Поле {field_name!r} пустое")
    return pd.to_datetime(value, dayfirst=False, errors="raise").normalize()


def years_between(valuation_date, expiry_date) -> float:
    valuation = parse_date(valuation_date, "Valuation Date")
    expiry = parse_date(expiry_date, "Expiry Date")
    return float((expiry - valuation) / pd.Timedelta(days=365))


def normalize_instrument(value: str) -> str:
    text = _clean_str(value, "Option").lower()
    aliases = {
        "option": "Option", "opt": "Option", "опцион": "Option",
        "future": "Future", "futures": "Future", "fwd": "Future", "forward": "Future", "фьючерс": "Future",
        "spot": "Spot", "cash": "Spot", "спот": "Spot",
    }
    out = aliases.get(text, _clean_str(value, "Option"))
    if out not in SUPPORTED_INSTRUMENTS:
        raise ValueError(f"Instrument должен быть Option / Future / Spot, получено: {value!r}")
    return out


def normalize_side(value: str) -> str:
    text = _clean_str(value, "Buy").lower()
    aliases = {"buy": "Buy", "long": "Buy", "b": "Buy", "купить": "Buy", "покупка": "Buy",
               "sell": "Sell", "short": "Sell", "s": "Sell", "продать": "Sell", "продажа": "Sell"}
    out = aliases.get(text, _clean_str(value, "Buy").capitalize())
    if out not in SUPPORTED_SIDES:
        raise ValueError(f"Side должен быть Buy или Sell, получено: {value!r}")
    return out


def side_sign(side: str) -> int:
    return 1 if normalize_side(side) == "Buy" else -1


def normalize_option_type(value: str) -> str:
    text = _clean_str(value, "Call").capitalize()
    if text not in SUPPORTED_OPTION_TYPES:
        raise ValueError(f"Option Type должен быть Call или Put, получено: {value!r}")
    return text


def normalize_style(value: str) -> str:
    text = _clean_str(value, "European").lower()
    aliases = {"european": "European", "euro": "European", "eur": "European",
               "american": "American", "amer": "American", "us": "American"}
    out = aliases.get(text, _clean_str(value, "European").capitalize())
    if out not in SUPPORTED_STYLES:
        raise ValueError(f"Style должен быть European или American, получено: {value!r}")
    return out


def normalize_asset_type(value: str) -> str:
    text = _clean_str(value, "Equity").lower()
    aliases = {"equity": "Equity", "stock": "Equity", "index": "Index", "fx": "FX", "forex": "FX", "commodity": "Commodity"}
    out = aliases.get(text, _clean_str(value, "Equity"))
    if out not in SUPPORTED_ASSETS:
        raise ValueError(f"Asset Type должен быть Equity / Index / FX / Commodity, получено: {value!r}")
    return out


def standardize_strategy_columns(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()
    normalized = {str(c).strip().lower().replace("_", " "): c for c in out.columns}
    aliases = {
        "Instrument": ["instrument", "instrument type", "asset instrument", "тип инструмента", "инструмент"],
        "Side": ["side", "buy sell", "buy/sell", "сторона"],
        "Option Type": ["option type", "type", "call put", "call/put", "тип опциона"],
        "Quantity": ["quantity", "qty", "количество"],
        "Strike": ["strike", "k", "entry", "entry price", "strike / entry", "страйк", "цена входа"],
        "Expiry Date": ["expiry date", "expiry", "expiration", "maturity", "дата экспирации"],
        "Premium": ["premium", "price", "entry premium", "премия", "цена"],
        "Sigma": ["sigma", "vol", "volatility", "iv", "волатильность"],
        "Style": ["style", "option style", "стиль"],
        "Asset Type": ["asset type", "asset", "underlying", "underlying asset", "базовый актив"],
    }
    rename = {}
    for target, names in aliases.items():
        for name in names:
            if name in normalized:
                rename[normalized[name]] = target
                break
    out = out.rename(columns=rename)
    for col in STRATEGY_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[STRATEGY_COLUMNS]


def _forward_price(*, pricing_module, asset_type: str, S: float, T: float, Rd: float, Rf: float = 0.0, q: float = 0.0, valuation_date=None) -> float:

    asset_type = normalize_asset_type(asset_type)
    S = float(S)
    T = max(float(T), 0.0)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    try:
        if pricing_module is not None:
            if asset_type in ("Equity", "Index") and hasattr(pricing_module, "S_EQ_fwd"):
                return float(pricing_module.S_EQ_fwd(S=S, T=T, Rd=Rd, q=q).forward_price())
            if asset_type == "FX" and hasattr(pricing_module, "S_FX_fwd"):
                return float(pricing_module.S_FX_fwd(S=S, T=T, Rd=Rd, Rf=Rf).forward_price())
            if asset_type == "Commodity" and hasattr(pricing_module, "S_Commodity_fwd"):
                date_now = parse_date(valuation_date, "Valuation Date") if valuation_date is not None else pd.Timestamp.today().normalize()
                return float(pricing_module.S_Commodity_fwd(S=S, T=T, Rd=Rd, u=0.0, y=Rf, date_now=date_now, storage_payments=[]).forward_price())
    except Exception:
        pass

    if asset_type in ("Equity", "Index"):
        return float(S * np.exp((Rd - q) * T))
    return float(S * np.exp((Rd - Rf) * T))


def _price_option_leg(
    *,
    leg: dict,
    S: float,
    Rd: float,
    Rf: float,
    q: float,
    valuation_date,
    pricing_module,
    vol_surface_module,
    contract_multiplier: float,
    n_steps: int,
) -> dict[str, float]:
    asset_type = normalize_asset_type(leg.get("Asset Type", "Equity"))
    option_type = normalize_option_type(leg.get("Option Type", "Call"))
    style = normalize_style(leg.get("Style", "European"))
    K = _to_float(leg.get("Strike"), field_name="Strike")
    sigma = _to_float(leg.get("Sigma"), default=0.2, field_name="Sigma")
    expiry = parse_date(leg.get("Expiry Date"), "Expiry Date")
    T = years_between(valuation_date, expiry)
    if T <= 0:
        raise ValueError("Expiry Date должна быть позже Valuation Date")

    if vol_surface_module is None:
        vol_surface_module = load_vol_surface_module()
    if pricing_module is None:
        pricing_module = load_pricing_module()

    model_price = float(vol_surface_module.model_price(
        pricing_module=pricing_module,
        asset_type=asset_type,
        S=float(S),
        K=K,
        T=T,
        Rd=float(Rd),
        Rf=float(Rf),
        q=float(q),
        sigma=sigma,
        option_type=option_type,
        option_style=style,
        american_engine="Trinomial",
        n_steps=int(n_steps),
        poly_degree=3,
        div_dates="",
        div_amounts="",
        valuation_date=valuation_date,
    ))

    greeks = vol_surface_module.calculate_greeks(
        pricing_module=pricing_module,
        asset_type=asset_type,
        S=float(S),
        K=K,
        T=T,
        Rd=float(Rd),
        Rf=float(Rf),
        q=float(q),
        sigma=sigma,
        option_type=option_type,
        option_style=style,
        american_engine="Trinomial",
        n_steps=int(n_steps),
        poly_degree=3,
        div_dates="",
        div_amounts="",
        valuation_date=valuation_date,
    )
    return {"T": T, "Model Price": model_price, **greeks}


def _option_payoff(option_type: str, S_values, K: float) -> np.ndarray:
    option_type = normalize_option_type(option_type)
    S_values = np.asarray(S_values, dtype=float)
    if option_type == "Call":
        return np.maximum(S_values - float(K), 0.0)
    return np.maximum(float(K) - S_values, 0.0)


def _leg_payoff_profile(leg: dict, S_values, multiplier: float) -> np.ndarray:
    instrument = normalize_instrument(leg.get("Instrument", "Option"))
    sign = side_sign(leg.get("Side", "Buy"))
    qty = abs(_to_float(leg.get("Quantity"), default=1.0, field_name="Quantity"))
    S_values = np.asarray(S_values, dtype=float)

    if instrument == "Option":
        K = _to_float(leg.get("Strike"), field_name="Strike")
        premium = _to_float(leg.get("Premium"), default=0.0, field_name="Premium")
        payoff = _option_payoff(leg.get("Option Type", "Call"), S_values, K)
        return sign * qty * (payoff - premium) * multiplier

    if instrument == "Future":
        entry = _to_float(leg.get("Strike"), default=np.nan, field_name="Strike / Entry")
        if not np.isfinite(entry):
            entry = _to_float(leg.get("Premium"), default=0.0, field_name="Premium / Entry")
        return sign * qty * (S_values - entry) * multiplier


    entry = _to_float(leg.get("Premium"), default=np.nan, field_name="Premium / Entry")
    if not np.isfinite(entry):
        entry = _to_float(leg.get("Strike"), default=0.0, field_name="Strike / Entry")
    return sign * qty * (S_values - entry) * multiplier


def _leg_value_today(
    leg: dict,
    *,
    S: float,
    Rd: float,
    Rf: float,
    q: float,
    valuation_date,
    pricing_module,
    vol_surface_module,
    multiplier: float,
    n_steps: int,
) -> float:
    instrument = normalize_instrument(leg.get("Instrument", "Option"))
    sign = side_sign(leg.get("Side", "Buy"))
    qty = abs(_to_float(leg.get("Quantity"), default=1.0, field_name="Quantity"))
    premium = _to_float(leg.get("Premium"), default=0.0, field_name="Premium")

    if instrument == "Option":
        priced = _price_option_leg(
            leg=leg, S=max(float(S), 1e-8), Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date,
            pricing_module=pricing_module, vol_surface_module=vol_surface_module,
            contract_multiplier=multiplier, n_steps=n_steps,
        )
        return sign * qty * (priced["Model Price"] - premium) * multiplier

    if instrument == "Future":
        expiry = _clean_str(leg.get("Expiry Date"), "")
        T = years_between(valuation_date, expiry) if expiry else 0.0
        asset_type = normalize_asset_type(leg.get("Asset Type", "Equity"))
        model = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=S, T=T, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date)
        entry = _to_float(leg.get("Strike"), default=model, field_name="Strike / Entry")
        return sign * qty * (model - entry) * multiplier

    entry = _to_float(leg.get("Premium"), default=S, field_name="Premium / Entry")
    return sign * qty * (S - entry) * multiplier


def evaluate_strategy(
    legs: pd.DataFrame,
    *,
    S: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date=None,
    contract_multiplier: float = 1.0,
    pricing_module=None,
    vol_surface_module=None,
    n_steps: int = 200,
    s_min: Optional[float] = None,
    s_max: Optional[float] = None,
    n_points: int = 121,
) -> dict[str, Any]:

    if valuation_date is None:
        valuation_date = pd.Timestamp.today().normalize()
    valuation_date = parse_date(valuation_date, "Valuation Date")
    S = float(S)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    contract_multiplier = float(contract_multiplier)
    n_steps = int(n_steps)
    n_points = max(int(n_points), 21)

    if S <= 0:
        raise ValueError("S current должен быть > 0")
    if contract_multiplier <= 0:
        raise ValueError("Contract multiplier должен быть > 0")
    if n_steps <= 0:
        raise ValueError("n_steps должен быть > 0")

    legs_df = standardize_strategy_columns(legs)
    if legs_df.empty:
        raise ValueError("Стратегия пустая")

    if pricing_module is None:
        pricing_module = load_pricing_module()
    if vol_surface_module is None:
        vol_surface_module = load_vol_surface_module()

    result_rows = []
    strategy_price = 0.0
    total_pnl_today = 0.0
    net_premium_cashflow = 0.0
    totals = {"Delta": 0.0, "Gamma": 0.0, "Vega": 0.0, "Theta": 0.0, "Rho": 0.0}

    clean_legs: list[dict] = []
    for _, raw in legs_df.iterrows():
        leg = {col: raw.get(col, "") for col in STRATEGY_COLUMNS}
        clean_legs.append(leg)
        out = {col: leg.get(col, "") for col in LEG_RESULT_COLUMNS}
        try:
            instrument = normalize_instrument(leg.get("Instrument", "Option"))
            side = normalize_side(leg.get("Side", "Buy"))
            sign = side_sign(side)
            qty = abs(_to_float(leg.get("Quantity"), default=1.0, field_name="Quantity"))
            asset_type = normalize_asset_type(leg.get("Asset Type", "Equity"))
            premium = _to_float(leg.get("Premium"), default=0.0, field_name="Premium")
            style = normalize_style(leg.get("Style", "European")) if instrument == "Option" else ""
            option_type = normalize_option_type(leg.get("Option Type", "Call")) if instrument == "Option" else ""
            K = _to_float(leg.get("Strike"), default=np.nan, field_name="Strike / Entry")
            sigma = _to_float(leg.get("Sigma"), default=np.nan, field_name="Sigma")
            expiry_text = _clean_str(leg.get("Expiry Date"), "")

            model_price = np.nan
            leg_value = np.nan
            T = np.nan
            greeks = {"Delta": 0.0, "Gamma": 0.0, "Vega": 0.0, "Theta": 0.0, "Rho": 0.0}

            if instrument == "Option":
                if not np.isfinite(K):
                    raise ValueError("Для Option нужен Strike")
                if not np.isfinite(sigma):
                    raise ValueError("Для Option нужна Sigma")
                priced = _price_option_leg(
                    leg=leg, S=S, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date,
                    pricing_module=pricing_module, vol_surface_module=vol_surface_module,
                    contract_multiplier=contract_multiplier, n_steps=n_steps,
                )
                T = priced["T"]
                model_price = priced["Model Price"]
                greeks = {g: float(priced.get(g, np.nan)) for g in greeks}
                leg_value = sign * qty * (model_price - premium) * contract_multiplier
                strategy_price += sign * qty * model_price * contract_multiplier
                net_premium_cashflow += -sign * qty * premium * contract_multiplier

            elif instrument == "Future":
                T = years_between(valuation_date, expiry_text) if expiry_text else 0.0
                model_price = _forward_price(
                    pricing_module=pricing_module, asset_type=asset_type, S=S, T=T,
                    Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date,
                )
                entry = K if np.isfinite(K) else model_price
                leg_value = sign * qty * (model_price - entry) * contract_multiplier
                strategy_price += sign * qty * model_price * contract_multiplier

                h = max(abs(S) * 0.001, 0.01)
                model_up = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=S+h, T=T, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date)
                model_dn = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=max(S-h, 1e-8), T=T, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date)
                greeks["Delta"] = (model_up - model_dn) / ((S + h) - max(S - h, 1e-8))
                greeks["Gamma"] = 0.0
                r_up = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=S, T=T, Rd=Rd+0.0001, Rf=Rf, q=q, valuation_date=valuation_date)
                greeks["Rho"] = (r_up - model_price) / 0.0001

            else:
                entry = premium if np.isfinite(premium) and premium != 0 else (K if np.isfinite(K) else S)
                model_price = S
                leg_value = sign * qty * (S - entry) * contract_multiplier
                strategy_price += sign * qty * S * contract_multiplier
                greeks["Delta"] = 1.0

            total_pnl_today += leg_value
            for g, val in greeks.items():
                if np.isfinite(val):
                    totals[g] += sign * qty * val * contract_multiplier

            out.update({
                "Instrument": instrument,
                "Side": side,
                "Option Type": option_type,
                "Quantity": qty,
                "Strike": K if np.isfinite(K) else "",
                "Expiry Date": expiry_text,
                "Premium": premium,
                "Sigma": sigma if np.isfinite(sigma) else "",
                "Style": style,
                "Asset Type": asset_type,
                "T": T,
                "Model Price": model_price,
                "Leg Value": leg_value,
                "Delta": sign * qty * greeks["Delta"] * contract_multiplier if np.isfinite(greeks["Delta"]) else np.nan,
                "Gamma": sign * qty * greeks["Gamma"] * contract_multiplier if np.isfinite(greeks["Gamma"]) else np.nan,
                "Vega": sign * qty * greeks["Vega"] * contract_multiplier if np.isfinite(greeks["Vega"]) else np.nan,
                "Theta": sign * qty * greeks["Theta"] * contract_multiplier if np.isfinite(greeks["Theta"]) else np.nan,
                "Rho": sign * qty * greeks["Rho"] * contract_multiplier if np.isfinite(greeks["Rho"]) else np.nan,
                "Status": "OK",
            })
        except Exception as exc:
            out["Status"] = f"ERROR: {exc}"
        result_rows.append(out)

    leg_results = pd.DataFrame(result_rows, columns=LEG_RESULT_COLUMNS)

    if s_min is None:
        s_min = 0.0
    if s_max is None:
        strikes = pd.to_numeric(legs_df["Strike"], errors="coerce")
        max_ref = np.nanmax([S * 2.0, strikes.max() * 1.5 if np.isfinite(strikes.max()) else S * 2.0])
        s_max = max(float(max_ref), S * 1.25)
    s_min = max(float(s_min), 0.0)
    s_max = max(float(s_max), s_min + 1e-6)
    S_grid = np.linspace(s_min, s_max, n_points)

    payoff_profile = calculate_payoff_profile(clean_legs, S_grid, contract_multiplier)
    value_profile = calculate_value_profile(
        clean_legs,
        S_grid,
        Rd=Rd,
        Rf=Rf,
        q=q,
        valuation_date=valuation_date,
        pricing_module=pricing_module,
        vol_surface_module=vol_surface_module,
        contract_multiplier=contract_multiplier,
        n_steps=n_steps,
    )
    base_values = value_profile["Strategy Value"].to_numpy(dtype=float)
    delta_profile, gamma_profile = _delta_gamma_from_value_profile(S_grid, base_values)

    h_vol = 0.0001
    h_r = 0.0001
    h_t = 1 / 365
    vega_profile = np.full_like(base_values, np.nan, dtype=float)
    theta_profile = np.full_like(base_values, np.nan, dtype=float)
    rho_profile = np.full_like(base_values, np.nan, dtype=float)

    try:
        bumped_legs = standardize_strategy_columns(legs_df).copy()
        instr = bumped_legs["Instrument"].astype(str).str.strip().str.lower()
        is_option = instr.isin(["option", "opt", "опцион"])
        sigmas = pd.to_numeric(
            bumped_legs.loc[is_option, "Sigma"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
        bumped_legs["Sigma"] = bumped_legs["Sigma"].astype(object)
        bumped_legs.loc[is_option, "Sigma"] = sigmas.add(h_vol).astype(object)
        value_vol_up = calculate_value_profile(
            bumped_legs,
            S_grid,
            Rd=Rd,
            Rf=Rf,
            q=q,
            valuation_date=valuation_date,
            pricing_module=pricing_module,
            vol_surface_module=vol_surface_module,
            contract_multiplier=contract_multiplier,
            n_steps=n_steps,
        )["Strategy Value"].to_numpy(dtype=float)
        vega_profile = (value_vol_up - base_values) / h_vol
    except Exception:
        pass

    try:
        value_r_up = calculate_value_profile(
            clean_legs,
            S_grid,
            Rd=Rd + h_r,
            Rf=Rf,
            q=q,
            valuation_date=valuation_date,
            pricing_module=pricing_module,
            vol_surface_module=vol_surface_module,
            contract_multiplier=contract_multiplier,
            n_steps=n_steps,
        )["Strategy Value"].to_numpy(dtype=float)
        rho_profile = (value_r_up - base_values) / h_r
    except Exception:
        pass

    try:
        next_valuation_date = valuation_date + pd.Timedelta(days=1)
        value_t_down = calculate_value_profile(
            clean_legs,
            S_grid,
            Rd=Rd,
            Rf=Rf,
            q=q,
            valuation_date=next_valuation_date,
            pricing_module=pricing_module,
            vol_surface_module=vol_surface_module,
            contract_multiplier=contract_multiplier,
            n_steps=n_steps,
        )["Strategy Value"].to_numpy(dtype=float)
        theta_profile = (value_t_down - base_values) / h_t
    except Exception:
        pass

    profile_df = pd.DataFrame({
        "S": S_grid,
        "P/L at Expiry": payoff_profile,
        "Strategy Value Today": base_values,
        "Delta": delta_profile,
        "Gamma": gamma_profile,
        "Vega": vega_profile,
        "Theta": theta_profile,
        "Rho": rho_profile,
    })

    max_profit, max_loss = _max_profit_loss_from_profile(profile_df["S"].to_numpy(), profile_df["P/L at Expiry"].to_numpy())
    breakevens = _breakeven_points(profile_df["S"].to_numpy(), profile_df["P/L at Expiry"].to_numpy())

    summary = {
        "Strategy Price": strategy_price,
        "Total P/L Today": total_pnl_today,
        "Net Premium Cashflow": net_premium_cashflow,
        "Total Delta": totals["Delta"],
        "Total Gamma": totals["Gamma"],
        "Total Vega": totals["Vega"],
        "Total Theta": totals["Theta"],
        "Total Rho": totals["Rho"],
        "Max Profit": max_profit,
        "Max Loss": max_loss,
        "Breakeven Points": breakevens,
    }

    return {
        "legs": leg_results,
        "summary": summary,
        "profiles": profile_df,
        "input_legs": legs_df,
    }


def calculate_payoff_profile(legs: list[dict] | pd.DataFrame, S_values, contract_multiplier: float = 1.0) -> np.ndarray:
    if isinstance(legs, pd.DataFrame):
        records = standardize_strategy_columns(legs).to_dict("records")
    else:
        records = legs
    total = np.zeros_like(np.asarray(S_values, dtype=float), dtype=float)
    for leg in records:
        try:
            total += _leg_payoff_profile(leg, S_values, contract_multiplier)
        except Exception:

            continue
    return total


def calculate_value_profile(
    legs: list[dict] | pd.DataFrame,
    S_values,
    *,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date=None,
    pricing_module=None,
    vol_surface_module=None,
    contract_multiplier: float = 1.0,
    n_steps: int = 200,
) -> pd.DataFrame:
    if isinstance(legs, pd.DataFrame):
        records = standardize_strategy_columns(legs).to_dict("records")
    else:
        records = legs
    values = []
    for s in np.asarray(S_values, dtype=float):
        total = 0.0
        for leg in records:
            try:
                total += _leg_value_today(
                    leg,
                    S=float(s),
                    Rd=Rd,
                    Rf=Rf,
                    q=q,
                    valuation_date=valuation_date,
                    pricing_module=pricing_module,
                    vol_surface_module=vol_surface_module,
                    multiplier=contract_multiplier,
                    n_steps=n_steps,
                )
            except Exception:
                continue
        values.append(total)
    return pd.DataFrame({"S": np.asarray(S_values, dtype=float), "Strategy Value": values})


def _delta_gamma_from_value_profile(S_values: np.ndarray, values: np.ndarray):
    S_values = np.asarray(S_values, dtype=float)
    values = np.asarray(values, dtype=float)
    if len(S_values) < 3:
        return np.full_like(values, np.nan), np.full_like(values, np.nan)
    delta = np.gradient(values, S_values)
    gamma = np.gradient(delta, S_values)
    return delta, gamma


def _breakeven_points(S_values: np.ndarray, pnl: np.ndarray) -> list[float]:
    points: list[float] = []
    S_values = np.asarray(S_values, dtype=float)
    pnl = np.asarray(pnl, dtype=float)
    for i in range(len(S_values) - 1):
        y1, y2 = pnl[i], pnl[i + 1]
        x1, x2 = S_values[i], S_values[i + 1]
        if not (np.isfinite(y1) and np.isfinite(y2)):
            continue
        if abs(y1) < 1e-10:
            points.append(float(x1))
        elif y1 * y2 < 0:
            x = x1 - y1 * (x2 - x1) / (y2 - y1)
            points.append(float(x))
    unique = []
    for p in points:
        if not any(abs(p - q) < 1e-4 for q in unique):
            unique.append(p)
    return unique


def _max_profit_loss_from_profile(S_values: np.ndarray, pnl: np.ndarray) -> tuple[Any, Any]:
    S_values = np.asarray(S_values, dtype=float)
    pnl = np.asarray(pnl, dtype=float)
    finite = np.isfinite(pnl)
    if not finite.any():
        return np.nan, np.nan
    max_profit: Any = float(np.nanmax(pnl))
    max_loss: Any = float(np.nanmin(pnl))
    if len(S_values) >= 3:
        high_slope = (pnl[-1] - pnl[-3]) / max(S_values[-1] - S_values[-3], 1e-12)
        if np.isfinite(high_slope):
            if high_slope > 1e-8:
                max_profit = "Unlimited"
            elif high_slope < -1e-8:
                max_loss = "Unlimited"
    return max_profit, max_loss


def summary_to_dataframe(summary: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for k, v in summary.items():
        if isinstance(v, list):
            value = ", ".join(f"{x:.6f}" for x in v) if v else "—"
        else:
            value = v
        rows.append({"Metric": k, "Value": value})
    return pd.DataFrame(rows)


def _normalize_scenario_factor(value: str) -> str:
    text = _clean_str(value, "S").strip().lower()
    aliases = {
        "spot": "S", "underlying": "S", "underlying price": "S", "price": "S", "s": "S",
        "vol": "Volatility", "volatility": "Volatility", "sigma": "Volatility", "iv": "Volatility",
        "rd": "Rd", "rate": "Rd", "domestic rate": "Rd",
        "rf": "Rf", "foreign rate": "Rf", "carry": "Rf",
        "q": "q", "dividend": "q", "dividend yield": "q",
        "delta": "Delta", "gamma": "Gamma", "vega": "Vega", "theta": "Theta", "rho": "Rho",
    }
    out = aliases.get(text, _clean_str(value, "S"))
    if out not in RISK_MATRIX_SCENARIO_FACTORS:
        raise ValueError(f"Risk factor должен быть одним из {RISK_MATRIX_SCENARIO_FACTORS}, получено: {value!r}")
    return out


def _normalize_value_metric(value: str) -> tuple[str, str]:

    text = _clean_str(value, "Total P/L Today").strip().lower()
    aliases = {
        "total p/l today": ("Total P/L Today", "Strategy Value Today"),
        "p/l today": ("Total P/L Today", "Strategy Value Today"),
        "pl today": ("Total P/L Today", "Strategy Value Today"),
        "pnl today": ("Total P/L Today", "Strategy Value Today"),
        "strategy value today": ("Total P/L Today", "Strategy Value Today"),
        "value today": ("Total P/L Today", "Strategy Value Today"),
        "p/l at expiry": ("P/L at Expiry", "P/L at Expiry"),
        "pl at expiry": ("P/L at Expiry", "P/L at Expiry"),
        "pnl at expiry": ("P/L at Expiry", "P/L at Expiry"),
        "payoff": ("P/L at Expiry", "P/L at Expiry"),
        "strategy price": ("Strategy Price", "Strategy Price"),
        "price": ("Strategy Price", "Strategy Price"),
    }
    out = aliases.get(text)
    if out is None:
        original = _clean_str(value, "Total P/L Today")
        if original in RISK_MATRIX_VALUE_METRICS:
            return aliases[original.lower()]
        raise ValueError(f"Risk matrix value должен быть одним из {RISK_MATRIX_VALUE_METRICS}, получено: {value!r}")
    return out


def _normalize_percent_like(value: float) -> float:
    value = float(value)
    return value / 100.0 if abs(value) > 1.0 else value


def _format_factor_value(factor: str, value: float) -> str:
    factor = _normalize_scenario_factor(factor)
    value = float(value)
    if factor == "Volatility":
        return f"{_normalize_percent_like(value) * 100.0:.2f}%"
    if factor in ("Rd", "Rf", "q"):
        return f"{_normalize_percent_like(value) * 100.0:.2f}%"
    return f"{value:.6g}"


def _apply_direct_factor(state: dict[str, float], factor: str, value: float) -> None:
    factor = _normalize_scenario_factor(factor)
    if factor == "S":
        state["S"] = float(value)
    elif factor == "Volatility":
        state["volatility_override"] = _normalize_percent_like(value)
    elif factor in ("Rd", "Rf", "q"):
        state[factor] = _normalize_percent_like(value)
    else:
        raise ValueError(f"{factor} не является прямым входным параметром")


def _strategy_point_metrics(
    legs: pd.DataFrame,
    *,
    S: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date=None,
    contract_multiplier: float = 1.0,
    pricing_module=None,
    vol_surface_module=None,
    n_steps: int = 200,
    volatility_override: Optional[float] = None,
) -> dict[str, float]:

    if valuation_date is None:
        valuation_date = pd.Timestamp.today().normalize()
    valuation_date = parse_date(valuation_date, "Valuation Date")
    legs_df = standardize_strategy_columns(legs)
    if volatility_override is not None:
        instr = legs_df["Instrument"].astype(str).str.strip().str.lower()
        is_option = instr.isin(["option", "opt", "опцион"])
        legs_df.loc[is_option, "Sigma"] = float(volatility_override)

    S = float(S)
    Rd = float(Rd)
    Rf = float(Rf)
    q = float(q)
    contract_multiplier = float(contract_multiplier)
    n_steps = int(n_steps)

    if S <= 0:
        raise ValueError("S должен быть > 0")
    if contract_multiplier <= 0:
        raise ValueError("Contract multiplier должен быть > 0")

    pnl_expiry = float(calculate_payoff_profile(legs_df, np.array([S]), contract_multiplier)[0])

    if pricing_module is None:
        pricing_module = load_pricing_module()
    if vol_surface_module is None:
        vol_surface_module = load_vol_surface_module()

    strategy_price = 0.0
    pnl_today = 0.0
    totals = {"Delta": 0.0, "Gamma": 0.0, "Vega": 0.0, "Theta": 0.0, "Rho": 0.0}

    for _, raw in legs_df.iterrows():
        leg = {col: raw.get(col, "") for col in STRATEGY_COLUMNS}
        try:
            instrument = normalize_instrument(leg.get("Instrument", "Option"))
            side = normalize_side(leg.get("Side", "Buy"))
            sign = side_sign(side)
            qty = abs(_to_float(leg.get("Quantity"), default=1.0, field_name="Quantity"))
            asset_type = normalize_asset_type(leg.get("Asset Type", "Equity"))
            premium = _to_float(leg.get("Premium"), default=0.0, field_name="Premium")
            greeks = {"Delta": 0.0, "Gamma": 0.0, "Vega": 0.0, "Theta": 0.0, "Rho": 0.0}

            if instrument == "Option":
                priced = _price_option_leg(
                    leg=leg,
                    S=S,
                    Rd=Rd,
                    Rf=Rf,
                    q=q,
                    valuation_date=valuation_date,
                    pricing_module=pricing_module,
                    vol_surface_module=vol_surface_module,
                    contract_multiplier=contract_multiplier,
                    n_steps=n_steps,
                )
                model_price = float(priced["Model Price"])
                greeks = {g: float(priced.get(g, np.nan)) for g in greeks}
                strategy_price += sign * qty * model_price * contract_multiplier
                pnl_today += sign * qty * (model_price - premium) * contract_multiplier

            elif instrument == "Future":
                expiry_text = _clean_str(leg.get("Expiry Date"), "")
                T = years_between(valuation_date, expiry_text) if expiry_text else 0.0
                model_price = _forward_price(
                    pricing_module=pricing_module,
                    asset_type=asset_type,
                    S=S,
                    T=T,
                    Rd=Rd,
                    Rf=Rf,
                    q=q,
                    valuation_date=valuation_date,
                )
                entry = _to_float(leg.get("Strike"), default=model_price, field_name="Strike / Entry")
                strategy_price += sign * qty * model_price * contract_multiplier
                pnl_today += sign * qty * (model_price - entry) * contract_multiplier
                h = max(abs(S) * 0.001, 0.01)
                model_up = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=S + h, T=T, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date)
                model_dn = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=max(S - h, 1e-8), T=T, Rd=Rd, Rf=Rf, q=q, valuation_date=valuation_date)
                greeks["Delta"] = (model_up - model_dn) / ((S + h) - max(S - h, 1e-8))
                greeks["Gamma"] = 0.0
                r_up = _forward_price(pricing_module=pricing_module, asset_type=asset_type, S=S, T=T, Rd=Rd + 0.0001, Rf=Rf, q=q, valuation_date=valuation_date)
                greeks["Rho"] = (r_up - model_price) / 0.0001

            else:
                K = _to_float(leg.get("Strike"), default=np.nan, field_name="Strike / Entry")
                entry = premium if np.isfinite(premium) and premium != 0 else (K if np.isfinite(K) else S)
                model_price = S
                strategy_price += sign * qty * model_price * contract_multiplier
                pnl_today += sign * qty * (S - entry) * contract_multiplier
                greeks["Delta"] = 1.0

            for g, val in greeks.items():
                if np.isfinite(val):
                    totals[g] += sign * qty * val * contract_multiplier
        except Exception:
            continue

    return {
        "P/L at Expiry": pnl_expiry,
        "Strategy Value Today": pnl_today,
        "Strategy Price": strategy_price,
        "Delta": totals["Delta"],
        "Gamma": totals["Gamma"],
        "Vega": totals["Vega"],
        "Theta": totals["Theta"],
        "Rho": totals["Rho"],
    }


def _solve_s_for_target_metric(
    legs: pd.DataFrame,
    *,
    target_metric: str,
    target_value: float,
    base_state: dict[str, float],
    valuation_date,
    contract_multiplier: float,
    pricing_module,
    vol_surface_module,
    n_steps: int,
    s_min: float,
    s_max: float,
    n_grid: int,
) -> tuple[float, float]:

    n_grid = max(int(n_grid), 31)
    grid = np.linspace(max(float(s_min), 1e-8), max(float(s_max), float(s_min) + 1e-8), n_grid)
    values = []
    for s in grid:
        try:
            metrics = _strategy_point_metrics(
                legs,
                S=float(s),
                Rd=base_state["Rd"],
                Rf=base_state["Rf"],
                q=base_state["q"],
                valuation_date=valuation_date,
                contract_multiplier=contract_multiplier,
                pricing_module=pricing_module,
                vol_surface_module=vol_surface_module,
                n_steps=n_steps,
                volatility_override=base_state.get("volatility_override"),
            )
            values.append(float(metrics.get(target_metric, np.nan)))
        except Exception:
            values.append(np.nan)
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError(f"Не удалось рассчитать {target_metric} на сетке S для поиска target")
    idx_candidates = np.where(finite)[0]
    best_local = int(np.nanargmin(np.abs(values[finite] - float(target_value))))
    best_idx = int(idx_candidates[best_local])
    return float(grid[best_idx]), float(values[best_idx])


def calculate_two_factor_risk_matrix(
    legs: pd.DataFrame,
    *,
    row_factor: str,
    row_values,
    col_factor: str,
    col_values,
    value_metric: str = "Total P/L Today",
    S: float,
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date=None,
    contract_multiplier: float = 1.0,
    pricing_module=None,
    vol_surface_module=None,
    n_steps: int = 200,
    s_min: float = 0.0,
    s_max: Optional[float] = None,
    n_points: int = 81,
) -> dict[str, Any]:

    row_factor = _normalize_scenario_factor(row_factor)
    col_factor = _normalize_scenario_factor(col_factor)
    value_label, internal_value_key = _normalize_value_metric(value_metric)
    target_factors = {"Delta", "Gamma", "Vega", "Theta", "Rho"}

    row_values = np.asarray([float(x) for x in row_values], dtype=float)
    col_values = np.asarray([float(x) for x in col_values], dtype=float)
    row_values = row_values[np.isfinite(row_values)]
    col_values = col_values[np.isfinite(col_values)]
    if len(row_values) == 0 or len(col_values) == 0:
        raise ValueError("Для risk matrix нужны непустые значения rows и columns")

    if row_factor in target_factors and col_factor in target_factors:
        raise ValueError("Нельзя выбрать две Target Greek оси одновременно. Например, выбери Delta × Volatility или S × Volatility.")
    if (row_factor in target_factors and col_factor == "S") or (col_factor in target_factors and row_factor == "S"):
        raise ValueError("Target Greek уже подбирает S, поэтому не сочетай её с S. Например, выбери Delta × Volatility.")

    if pricing_module is None:
        pricing_module = load_pricing_module()
    if vol_surface_module is None:
        vol_surface_module = load_vol_surface_module()
    if valuation_date is None:
        valuation_date = pd.Timestamp.today().normalize()
    valuation_date = parse_date(valuation_date, "Valuation Date")

    if s_max is None:
        strikes = pd.to_numeric(standardize_strategy_columns(legs)["Strike"], errors="coerce")
        max_ref = np.nanmax([float(S) * 2.0, strikes.max() * 1.5 if np.isfinite(strikes.max()) else float(S) * 2.0])
        s_max = max(float(max_ref), float(S) * 1.25)
    s_min = max(float(s_min), 1e-8)
    s_max = max(float(s_max), s_min + 1e-8)

    row_labels = [_format_factor_value(row_factor, v) for v in row_values]
    col_labels = [_format_factor_value(col_factor, v) for v in col_values]
    rows = []
    long_rows = []

    for rv, rlabel in zip(row_values, row_labels):
        row_out = []
        for cv, clabel in zip(col_values, col_labels):
            state = {
                "S": float(S),
                "Rd": float(Rd),
                "Rf": float(Rf),
                "q": float(q),
                "volatility_override": None,
            }
            target_metric = None
            target_value = None
            try:
                for factor, value in ((row_factor, rv), (col_factor, cv)):
                    if factor in target_factors:
                        target_metric = factor
                        target_value = float(value)
                    else:
                        _apply_direct_factor(state, factor, float(value))

                actual_target_value = np.nan
                if target_metric is not None:
                    solved_s, actual_target_value = _solve_s_for_target_metric(
                        legs,
                        target_metric=target_metric,
                        target_value=float(target_value),
                        base_state=state,
                        valuation_date=valuation_date,
                        contract_multiplier=contract_multiplier,
                        pricing_module=pricing_module,
                        vol_surface_module=vol_surface_module,
                        n_steps=n_steps,
                        s_min=s_min,
                        s_max=s_max,
                        n_grid=n_points,
                    )
                    state["S"] = solved_s

                metrics = _strategy_point_metrics(
                    legs,
                    S=state["S"],
                    Rd=state["Rd"],
                    Rf=state["Rf"],
                    q=state["q"],
                    valuation_date=valuation_date,
                    contract_multiplier=contract_multiplier,
                    pricing_module=pricing_module,
                    vol_surface_module=vol_surface_module,
                    n_steps=n_steps,
                    volatility_override=state.get("volatility_override"),
                )
                value = float(metrics.get(internal_value_key, np.nan))
                status = "OK"
            except Exception as exc:
                value = np.nan
                actual_target_value = np.nan
                status = f"ERROR: {exc}"
            row_out.append(value)
            long_rows.append({
                "Row Factor": row_factor,
                "Row Value": float(rv),
                "Row Label": rlabel,
                "Column Factor": col_factor,
                "Column Value": float(cv),
                "Column Label": clabel,
                "Value Metric": value_label,
                "Value": value,
                "Scenario S": state.get("S", np.nan) if 'state' in locals() else np.nan,
                "Scenario Volatility": state.get("volatility_override", np.nan) if 'state' in locals() else np.nan,
                "Target Greek Actual": actual_target_value,
                "Status": status,
            })
        rows.append(row_out)

    matrix_raw = pd.DataFrame(rows, index=row_labels, columns=col_labels)
    matrix_raw.index.name = row_factor
    matrix = matrix_raw.reset_index()
    long_df = pd.DataFrame(long_rows)
    return {
        "row_factor": row_factor,
        "col_factor": col_factor,
        "value_metric": value_label,
        "internal_value_key": internal_value_key,
        "matrix": matrix,
        "matrix_raw": matrix_raw,
        "long": long_df,
        "row_values": row_values,
        "col_values": col_values,
    }


def calculate_risk_matrix(
    legs: pd.DataFrame,
    *,
    s_values,
    vol_values,
    metric: str = "Total P/L Today",
    Rd: float,
    Rf: float = 0.0,
    q: float = 0.0,
    valuation_date=None,
    contract_multiplier: float = 1.0,
    pricing_module=None,
    vol_surface_module=None,
    n_steps: int = 200,
) -> dict[str, Any]:
    return calculate_two_factor_risk_matrix(
        legs,
        row_factor="S",
        row_values=s_values,
        col_factor="Volatility",
        col_values=vol_values,
        value_metric=metric,
        S=float(np.mean([float(x) for x in s_values])),
        Rd=Rd,
        Rf=Rf,
        q=q,
        valuation_date=valuation_date,
        contract_multiplier=contract_multiplier,
        pricing_module=pricing_module,
        vol_surface_module=vol_surface_module,
        n_steps=n_steps,
        s_min=min(float(x) for x in s_values),
        s_max=max(float(x) for x in s_values),
        n_points=max(len(list(s_values)), 41),
    )

def export_to_excel(result: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    with pd.ExcelWriter(path) as writer:
        result.get("input_legs", pd.DataFrame()).to_excel(writer, sheet_name="Input Legs", index=False)
        result.get("legs", pd.DataFrame()).to_excel(writer, sheet_name="Leg Results", index=False)
        summary_to_dataframe(result.get("summary", {})).to_excel(writer, sheet_name="Summary", index=False)
        result.get("profiles", pd.DataFrame()).to_excel(writer, sheet_name="Profiles", index=False)
        risk = result.get("risk_matrix")
        if isinstance(risk, dict):
            risk.get("matrix", pd.DataFrame()).to_excel(writer, sheet_name="Risk Matrix", index=False)
            risk.get("long", pd.DataFrame()).to_excel(writer, sheet_name="Risk Matrix Long", index=False)


def save_strategy(legs: pd.DataFrame, common_params: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    data = {
        "common_params": common_params,
        "legs": standardize_strategy_columns(legs).to_dict("records"),
    }
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    elif path.suffix.lower() == ".csv":
        standardize_strategy_columns(legs).to_csv(path, index=False)
    elif path.suffix.lower() in (".xlsx", ".xls"):
        standardize_strategy_columns(legs).to_excel(path, index=False)
    else:
        raise ValueError("Поддерживаются JSON, CSV, XLSX, XLS")


def load_strategy(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        legs = pd.DataFrame(data.get("legs", []))
        return {"common_params": data.get("common_params", {}), "legs": standardize_strategy_columns(legs)}
    if suffix == ".csv":
        return {"common_params": {}, "legs": standardize_strategy_columns(pd.read_csv(path))}
    if suffix in (".xlsx", ".xls"):
        return {"common_params": {}, "legs": standardize_strategy_columns(pd.read_excel(path))}
    raise ValueError("Поддерживаются JSON, CSV, XLSX, XLS")


if __name__ == "__main__":
    pricing = load_pricing_module()
    volsurf = load_vol_surface_module()
    demo_legs = pd.DataFrame([
        {"Instrument": "Option", "Side": "Buy", "Option Type": "Call", "Quantity": 1, "Strike": 60, "Expiry Date": "2026-09-01", "Premium": 5.1, "Sigma": 0.24, "Style": "European", "Asset Type": "Equity"},
        {"Instrument": "Option", "Side": "Sell", "Option Type": "Call", "Quantity": 1, "Strike": 70, "Expiry Date": "2026-09-01", "Premium": 1.8, "Sigma": 0.24, "Style": "European", "Asset Type": "Equity"},
        {"Instrument": "Spot", "Side": "Buy", "Option Type": "", "Quantity": 1, "Strike": "", "Expiry Date": "", "Premium": 62.16, "Sigma": "", "Style": "", "Asset Type": "Equity"},
    ])
    res = evaluate_strategy(demo_legs, S=62.16, Rd=0.0425, q=0.0, valuation_date="2026-06-15", pricing_module=pricing, vol_surface_module=volsurf)
    print(res["legs"].to_string(index=False))
    print(summary_to_dataframe(res["summary"]).to_string(index=False))
