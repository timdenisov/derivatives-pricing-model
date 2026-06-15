from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = [
    "Ticker",
    "Expiry Date",
    "Strike",
    "Option Type",
    "Bid",
    "Ask",
    "Last",
    "Market Price",
    "Volume",
    "Open Interest",
    "Underlying Price",
    "Sigma",
]

ALIASES = {
    "Ticker": ["ticker", "symbol", "secid", "instrument", "contract", "code", "тикер", "инструмент"],
    "Expiry Date": ["expiry date", "expiry", "expiration", "maturity", "exp date", "date expiration", "дата экспирации", "экспирация", "срок"],
    "Strike": ["strike", "k", "strike price", "страйк", "цена исполнения"],
    "Option Type": ["option type", "type", "call put", "call/put", "cp", "right", "тип опциона", "тип"],
    "Bid": ["bid", "best bid", "bid price", "bid_price", "покупка", "бид"],
    "Ask": ["ask", "offer", "best ask", "ask price", "ask_price", "продажа", "аск"],
    "Last": ["last", "last price", "close", "settle", "settlement", "last_price", "последняя", "закрытие"],
    "Market Price": ["market price", "price", "mid", "mid price", "option price", "premium", "mark", "рыночная цена", "цена", "премия"],
    "Volume": ["volume", "vol", "объем", "объём"],
    "Open Interest": ["open interest", "oi", "open_interest", "открытый интерес"],
    "Underlying Price": ["underlying price", "underlying", "spot", "spot price", "s", "s current", "цена базового актива", "спот"],
    "Sigma": ["sigma", "iv", "implied vol", "implied volatility", "volatility", "impl vol", "vol", "волатильность"],
}

REQUIRED_FOR_VOL_SURFACE = ["Strike", "Expiry Date", "Market Price", "Option Type"]
REQUIRED_FOR_STRATEGY = ["Strike", "Expiry Date", "Market Price", "Option Type"]


def _norm_name(name: Any) -> str:
    return str(name).strip().lower().replace("_", " ").replace("-", " ").replace("/", " ")


def load_market_chain(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp1251")
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    raise ValueError("Поддерживаются только CSV, XLSX и XLS файлы")


def save_market_chain_template(path: str | Path) -> None:
    path = Path(path)
    rows = [
        {
            "Ticker": "D-C-20260901-60",
            "Expiry Date": "2026-09-01",
            "Strike": 60,
            "Option Type": "Call",
            "Bid": 5.00,
            "Ask": 5.20,
            "Last": 5.10,
            "Market Price": "",
            "Volume": 120,
            "Open Interest": 900,
            "Underlying Price": 62.16,
            "Sigma": 0.24,
        },
        {
            "Ticker": "D-P-20260901-60",
            "Expiry Date": "2026-09-01",
            "Strike": 60,
            "Option Type": "Put",
            "Bid": 2.60,
            "Ask": 2.80,
            "Last": 2.70,
            "Market Price": "",
            "Volume": 80,
            "Open Interest": 700,
            "Underlying Price": 62.16,
            "Sigma": 0.25,
        },
    ]
    df = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() in (".xlsx", ".xls"):
        with pd.ExcelWriter(path) as writer:
            df.to_excel(writer, sheet_name="Market Chain", index=False)
            pd.DataFrame({
                "Column": CANONICAL_COLUMNS,
                "Description": [
                    "Ticker / contract code",
                    "Expiry date, e.g. 2026-09-01",
                    "Option strike",
                    "Call or Put",
                    "Best bid",
                    "Best ask",
                    "Last traded / close / settlement price",
                    "Optional ready market price. If empty, Mid=(Bid+Ask)/2 is used, then Last.",
                    "Trading volume",
                    "Open interest",
                    "Underlying spot/current price",
                    "Optional volatility for Option Strategy",
                ],
            }).to_excel(writer, sheet_name="Column Guide", index=False)
    else:
        raise ValueError("Шаблон можно сохранить как CSV или XLSX")


def auto_mapping(columns) -> dict[str, str]:
    columns = list(columns)
    normalized_to_original = {_norm_name(c): c for c in columns}
    mapping: dict[str, str] = {}
    used = set()
    for target, aliases in ALIASES.items():
        found = ""
        for alias in aliases:
            key = _norm_name(alias)
            if key in normalized_to_original and normalized_to_original[key] not in used:
                found = normalized_to_original[key]
                break
        if not found:

            key = _norm_name(target)
            if key in normalized_to_original and normalized_to_original[key] not in used:
                found = normalized_to_original[key]
        mapping[target] = found
        if found:
            used.add(found)
    return mapping


def _series_from_mapping(df: pd.DataFrame, source_col: str) -> pd.Series:
    if source_col and source_col in df.columns:
        return df[source_col]
    return pd.Series([np.nan] * len(df), index=df.index)


def _to_numeric_series(s: pd.Series) -> pd.Series:
    text = s.astype(str).str.strip().str.replace(",", ".", regex=False)
    text = text.mask(text.str.lower().isin(["", "nan", "none", "nat"]))
    return pd.to_numeric(text, errors="coerce")


def normalize_option_type(value: Any, default: str = "Call") -> str:
    text = str(value).strip().lower()
    if text in ("c", "call", "колл", "калл", "покупка call"):
        return "Call"
    if text in ("p", "put", "пут", "путт", "продажа put"):
        return "Put"
    if default.capitalize() in ("Call", "Put"):
        return default.capitalize()
    return "Call"


def standardize_market_chain(
    raw: pd.DataFrame,
    mapping: Optional[dict[str, str]] = None,
    *,
    default_option_type: str = "Call",
) -> pd.DataFrame:

    if raw is None or raw.empty:
        raise ValueError("Файл market chain пустой")
    mapping = mapping or auto_mapping(raw.columns)
    out = pd.DataFrame(index=raw.index)

    for target in CANONICAL_COLUMNS:
        out[target] = _series_from_mapping(raw, mapping.get(target, ""))

    for col in ["Strike", "Bid", "Ask", "Last", "Market Price", "Volume", "Open Interest", "Underlying Price", "Sigma"]:
        out[col] = _to_numeric_series(out[col])

    out["Expiry Date"] = pd.to_datetime(out["Expiry Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Option Type"] = out["Option Type"].apply(lambda x: normalize_option_type(x, default_option_type))
    out["Ticker"] = out["Ticker"].fillna("").astype(str)

    mid = (out["Bid"] + out["Ask"]) / 2.0
    out["Mid Price"] = mid.where(out["Bid"].notna() & out["Ask"].notna())


    price = out["Market Price"].copy()
    price = price.where(price.notna(), out["Mid Price"])
    price = price.where(price.notna(), out["Last"])
    price = price.where(price.notna(), out["Bid"])
    price = price.where(price.notna(), out["Ask"])
    out["Market Price"] = price

    status = []
    for _, row in out.iterrows():
        errors = []
        if not np.isfinite(row.get("Strike", np.nan)) or float(row.get("Strike", np.nan)) <= 0:
            errors.append("Strike")
        if not isinstance(row.get("Expiry Date", None), str) or row.get("Expiry Date", "") in ("NaT", "nan", "None", ""):
            errors.append("Expiry Date")
        if not np.isfinite(row.get("Market Price", np.nan)) or float(row.get("Market Price", np.nan)) <= 0:
            errors.append("Market Price")
        if row.get("Option Type") not in ("Call", "Put"):
            errors.append("Option Type")
        status.append("OK" if not errors else "ERROR: " + ", ".join(errors))
    out["Status"] = status

    preferred = [
        "Ticker", "Expiry Date", "Strike", "Option Type", "Bid", "Ask", "Last", "Mid Price", "Market Price",
        "Volume", "Open Interest", "Underlying Price", "Sigma", "Status",
    ]
    return out[preferred]


def first_underlying_price(df: pd.DataFrame) -> Optional[float]:
    if df is None or df.empty or "Underlying Price" not in df.columns:
        return None
    s = pd.to_numeric(df["Underlying Price"], errors="coerce").dropna()
    if s.empty:
        return None
    value = float(s.iloc[0])
    return value if np.isfinite(value) and value > 0 else None


def prepare_vol_surface_data(normalized: pd.DataFrame, *, only_ok: bool = True) -> pd.DataFrame:
    if normalized is None or normalized.empty:
        raise ValueError("Нет нормализованных данных для Vol Surface")
    df = normalized.copy()
    if only_ok and "Status" in df.columns:
        df = df[df["Status"].astype(str) == "OK"].copy()
    out = pd.DataFrame({
        "Ticker": df.get("Ticker", ""),
        "Strike": df["Strike"],
        "Expiry Date": df["Expiry Date"],
        "Market Price": df["Market Price"],
        "Option Type": df["Option Type"],
    })
    if out.empty:
        raise ValueError("Нет OK-строк для отправки в Vol Surface")
    return out


def prepare_strategy_legs(
    normalized: pd.DataFrame,
    *,
    side: str = "Buy",
    quantity: float = 1.0,
    style: str = "European",
    asset_type: str = "Equity",
    sigma_source: str = "Sigma",
    fixed_sigma: float = 0.2,
    only_ok: bool = True,
) -> pd.DataFrame:
    if normalized is None or normalized.empty:
        raise ValueError("Нет нормализованных данных для Option Strategy")
    df = normalized.copy()
    if only_ok and "Status" in df.columns:
        df = df[df["Status"].astype(str) == "OK"].copy()
    if df.empty:
        raise ValueError("Нет OK-строк для отправки в Option Strategy")

    if str(sigma_source).lower().startswith("fixed"):
        sigma = pd.Series([float(fixed_sigma)] * len(df), index=df.index)
    else:
        sigma = pd.to_numeric(df.get("Sigma", np.nan), errors="coerce")
        sigma = sigma.where(sigma.notna(), float(fixed_sigma))

    out = pd.DataFrame({
        "Instrument": "Option",
        "Side": side,
        "Option Type": df["Option Type"],
        "Quantity": float(quantity),
        "Strike": df["Strike"],
        "Expiry Date": df["Expiry Date"],
        "Premium": df["Market Price"],
        "Sigma": sigma,
        "Style": style,
        "Asset Type": asset_type,
    })
    return out
