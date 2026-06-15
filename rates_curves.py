from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any, Optional
import html
import re

import numpy as np
import pandas as pd
import requests


@dataclass(frozen=True)
class CurvePointSpec:
    label: str
    period: float
    source_column: str = ""


USD_TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
)

CHINAMONEY_REALTIME_URLS = (
    "https://www.chinamoney.com.cn/english/bmkycvrty/",
    "https://www.chinamoney.org.cn/english/bmkycvrty/",
)


TREASURY_MATURITIES: tuple[CurvePointSpec, ...] = (
    CurvePointSpec("1M", 1 / 12, "1 Mo"),
    CurvePointSpec("1.5M", 1.5 / 12, "1.5 Mo"),
    CurvePointSpec("2M", 2 / 12, "2 Mo"),
    CurvePointSpec("3M", 3 / 12, "3 Mo"),
    CurvePointSpec("4M", 4 / 12, "4 Mo"),
    CurvePointSpec("6M", 6 / 12, "6 Mo"),
    CurvePointSpec("1Y", 1.0, "1 Yr"),
    CurvePointSpec("2Y", 2.0, "2 Yr"),
    CurvePointSpec("3Y", 3.0, "3 Yr"),
    CurvePointSpec("5Y", 5.0, "5 Yr"),
    CurvePointSpec("7Y", 7.0, "7 Yr"),
    CurvePointSpec("10Y", 10.0, "10 Yr"),
    CurvePointSpec("20Y", 20.0, "20 Yr"),
    CurvePointSpec("30Y", 30.0, "30 Yr"),
)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_date(value: Any) -> pd.Timestamp:
    if value is None or str(value).strip() == "":
        return pd.Timestamp.today().normalize()
    return pd.to_datetime(value, errors="raise").normalize()


def _to_numeric(value: Any) -> float:
    if value is None:
        return np.nan
    text = str(value).strip().replace(",", ".").replace("%", "")
    if text == "" or text.upper() in {"N/A", "NA", "NAN", "NONE", "NULL", "--", "—"}:
        return np.nan
    return float(text)


def label_to_years(label: str) -> float:

    original = _clean_text(label)
    text = (
        original.upper()
        .replace(" ", "")
        .replace("年", "Y")
        .replace("月", "M")
        .replace("日", "D")
        .replace("天", "D")
        .replace("周", "W")
    )
    if text in {"O/N", "ON", "OVERNIGHT"}:
        return 1.0 / 365.0

    if re.fullmatch(r"[+-]?\d+(?:[\.,]\d+)?", text):
        return float(text.replace(",", "."))

    match = re.search(r"([+-]?\d+(?:[\.,]\d+)?)([A-Z]+)?", text)
    if not match:
        raise ValueError(f"Не удалось определить срок из label: {label!r}")
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2) or "Y"

    if unit.startswith("D"):
        return value / 365.0
    if unit.startswith("W"):
        return value / 52.0
    if unit.startswith("M"):
        return value / 12.0
    return value


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [" ".join(_clean_text(x) for x in col if _clean_text(x)) for col in out.columns]
    else:
        out.columns = [_clean_text(c) for c in out.columns]
    out = out.dropna(how="all")
    return out


def _promote_header_if_needed(df: pd.DataFrame) -> pd.DataFrame:

    df = _normalise_columns(df)
    joined_columns = " ".join(map(str, df.columns)).lower()
    if any(token in joined_columns for token in ("date", "日期", "maturity", "期限", "yield", "收益率")):
        return df

    sample = df.head(8).copy()
    for idx, row in sample.iterrows():
        text = " ".join(_clean_text(v).lower() for v in row.tolist())
        if any(token in text for token in ("date", "日期", "maturity", "期限", "yield", "收益率")):
            new_df = df.loc[idx + 1:].copy()
            new_df.columns = [_clean_text(v) or f"col_{i}" for i, v in enumerate(row.tolist())]
            return _normalise_columns(new_df)
    return df


def _find_date_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        name = _clean_text(col).lower()
        if "date" in name or "日期" in name:
            return col
    best_col = None
    best_count = 0
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        count = int(parsed.notna().sum())
        if count > best_count:
            best_col, best_count = col, count
    return best_col if best_count > 0 else None


def _find_col_by_keywords(df: pd.DataFrame, keywords: tuple[str, ...]) -> Optional[str]:
    for col in df.columns:
        name = _clean_text(col).lower()
        if any(k.lower() in name for k in keywords):
            return col
    return None


def _filter_latest_on_or_before(df: pd.DataFrame, date_col: str, target_date: pd.Timestamp) -> tuple[pd.DataFrame, str]:
    temp = df.copy()
    temp["__date"] = pd.to_datetime(temp[date_col], errors="coerce").dt.normalize()
    temp = temp[temp["__date"].notna()]
    temp = temp[temp["__date"] <= target_date].sort_values("__date")
    if temp.empty:
        raise ValueError(f"Нет наблюдений на дату <= {target_date.date()}")
    obs_date = pd.Timestamp(temp["__date"].iloc[-1]).strftime("%Y-%m-%d")
    return temp[temp["__date"] == temp["__date"].iloc[-1]].copy(), obs_date


def _curve_rows_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        raise ValueError("Кривая не содержит ни одной числовой точки")
    df = pd.DataFrame(rows)
    df["period"] = pd.to_numeric(df["period"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["period", "value"]).sort_values("period").reset_index(drop=True)
    if df.empty:
        raise ValueError("После очистки кривая не содержит числовых period/value")
    return df


def _read_treasury_year(year: int) -> pd.DataFrame:
    params = {
        "type": "daily_treasury_yield_curve",
        "field_tdr_date_value": str(int(year)),
    }
    response = requests.get(USD_TREASURY_URL, params=params, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    for table in tables:
        df = _normalise_columns(table)
        if "Date" in df.columns and any(spec.source_column in df.columns for spec in TREASURY_MATURITIES):
            return df
    raise ValueError(f"Не удалось найти таблицу Daily Treasury Rates за {year}")


def get_us_treasury_curve(date: Any, *, max_lookback_years: int = 1) -> pd.DataFrame:

    target_date = _to_date(date)
    last_error: Optional[Exception] = None

    for shift in range(max_lookback_years + 1):
        year = int(target_date.year) - shift
        try:
            raw = _read_treasury_year(year)
            raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce").dt.normalize()
            raw = raw[raw["Date"].notna()]
            raw = raw[raw["Date"] <= target_date].sort_values("Date")
            if raw.empty:
                raise ValueError(f"Нет Treasury observations на дату <= {target_date.date()} в {year}")
            row = raw.iloc[-1]
            obs_date = pd.Timestamp(row["Date"]).strftime("%Y-%m-%d")
            rows = []
            for spec in TREASURY_MATURITIES:
                value = _to_numeric(row.get(spec.source_column, np.nan))
                rows.append({
                    "Currency": "USD",
                    "Label": spec.label,
                    "period": spec.period,
                    "value": value,
                    "Observation Date": obs_date,
                    "Source": "U.S. Treasury Daily Treasury Par Yield Curve Rates",
                    "Status": "OK" if np.isfinite(value) else f"ERROR: пустая точка {spec.source_column}",
                })
            out = pd.DataFrame(rows)
            ok = out[out["Status"].astype(str) == "OK"].copy()
            if ok.empty:
                raise ValueError("В выбранной строке Treasury нет числовых ставок")
            return out.sort_values("period").reset_index(drop=True)
        except Exception as exc:
            last_error = exc
            continue

    raise ValueError(f"Не удалось загрузить USD Treasury curve: {last_error}")


def _response_text(response: requests.Response) -> str:

    if response.encoding:
        try:
            return response.text
        except Exception:
            pass
    for encoding in ("utf-8", "gb18030", "gbk", "latin1"):
        try:
            return response.content.decode(encoding, errors="ignore")
        except Exception:
            continue
    return response.text


def _download_chinamoney_realtime_page() -> tuple[str, str, str]:

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    errors: list[str] = []
    for url in CHINAMONEY_REALTIME_URLS:
        try:
            response = requests.get(url, timeout=45, headers=headers)
            response.raise_for_status()
            text = _response_text(response)
            if not text or len(text.strip()) < 200:
                raise ValueError("ответ слишком короткий")
            date_header = response.headers.get("Date", "")
            return text, response.url, date_header
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("Не удалось скачать ChinaMoney CFETS Real-time Yield Curves: " + " | ".join(errors))


def _guess_observation_date(date_header: str = "") -> str:

    if date_header:
        try:
            return pd.to_datetime(date_header, errors="raise", utc=True).strftime("%Y-%m-%d")
        except Exception:
            pass
    return pd.Timestamp.today().normalize().strftime("%Y-%m-%d")


def _term_label(period: float) -> str:
    period = float(period)
    mapping = {
        1 / 12: "1M",
        0.25: "3M",
        0.5: "6M",
        0.75: "9M",
        1.0: "1Y",
        2.0: "2Y",
        3.0: "3Y",
        5.0: "5Y",
        7.0: "7Y",
        10.0: "10Y",
        15.0: "15Y",
        20.0: "20Y",
        30.0: "30Y",
        40.0: "40Y",
        50.0: "50Y",
    }
    for k, v in mapping.items():
        if abs(period - k) < 1e-8:
            return v
    return f"{period:g}Y"


def _deduplicate_curve_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    by_period: dict[float, dict[str, Any]] = {}
    for row in rows:
        try:
            period = float(row.get("period", np.nan))
            value = float(row.get("value", np.nan))
        except Exception:
            continue
        if not (np.isfinite(period) and np.isfinite(value)):
            continue
        key = round(period, 10)


        if key not in by_period:
            row = dict(row)
            row["period"] = period
            row["value"] = value
            by_period[key] = row
    return _curve_rows_dataframe(list(by_period.values()))


def _parse_chinamoney_realtime_table(table: pd.DataFrame, *, observation_date: str, source_url: str) -> pd.DataFrame:

    df = _promote_header_if_needed(table)
    df = df.dropna(how="all").copy()
    if df.empty:
        raise ValueError("Пустая таблица ChinaMoney")

    term_col = _find_col_by_keywords(df, ("standard term", "term", "maturity", "期限", "标准期限"))
    bid_col = _find_col_by_keywords(df, ("best bid", "bid", "买入", "报买"))
    ask_col = _find_col_by_keywords(df, ("best ask", "ask", "卖出", "报卖"))
    mid_col = _find_col_by_keywords(df, ("mid", "mean", "average", "均值", "中间"))

    if term_col is None:
        raise ValueError("Не найдена колонка срока/Standard Term")
    if mid_col is None and (bid_col is None or ask_col is None):
        raise ValueError("Не найдены колонки Mid либо Best Bid/Best Ask")

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        try:
            period = label_to_years(row.get(term_col, ""))
            if mid_col is not None:
                value = _to_numeric(row.get(mid_col, np.nan))
                bid = _to_numeric(row.get(bid_col, np.nan)) if bid_col else np.nan
                ask = _to_numeric(row.get(ask_col, np.nan)) if ask_col else np.nan
            else:
                bid = _to_numeric(row.get(bid_col, np.nan))
                ask = _to_numeric(row.get(ask_col, np.nan))
                value = (bid + ask) / 2.0
        except Exception:
            continue
        if np.isfinite(period) and np.isfinite(value):
            rows.append({
                "Currency": "CNY",
                "Label": _term_label(period),
                "period": period,
                "value": value,
                "Best Bid": bid if np.isfinite(bid) else "",
                "Best Ask": ask if np.isfinite(ask) else "",
                "Observation Date": observation_date,
                "Source": "ChinaMoney CFETS Real-time Yield Curves",
                "Source URL": source_url,
                "Status": "OK",
            })
    return _deduplicate_curve_rows(rows)


def _html_to_plain_text(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(?:p|div|tr|li|h\d|table)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _parse_chinamoney_realtime_text(text: str, *, observation_date: str, source_url: str) -> pd.DataFrame:

    plain = _html_to_plain_text(text)
    rows: list[dict[str, Any]] = []


    row_pattern = re.compile(
        r"^(?P<term>0\.083|0\.25|0\.5|0\.75|1|2|3|5|7|10|15|20|30|40|50)\s+"
        r"(?P<bond>.+?)\s+"
        r"(?P<bond_maturity>\d+(?:\.\d+)?)\s+"
        r"(?P<bid>\d+(?:\.\d+)?)\s+"
        r"(?P<ask>\d+(?:\.\d+)?)$"
    )
    for line in plain.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        match = row_pattern.match(line)
        if not match:
            continue
        try:
            period = label_to_years(match.group("term"))
            bid = _to_numeric(match.group("bid"))
            ask = _to_numeric(match.group("ask"))
            value = (bid + ask) / 2.0
        except Exception:
            continue
        if np.isfinite(period) and np.isfinite(value):
            rows.append({
                "Currency": "CNY",
                "Label": _term_label(period),
                "period": period,
                "value": value,
                "Best Bid": bid,
                "Best Ask": ask,
                "Observation Date": observation_date,
                "Source": "ChinaMoney CFETS Real-time Yield Curves",
                "Source URL": source_url,
                "Status": "OK",
            })
    return _deduplicate_curve_rows(rows)


def get_chinamoney_cny_curve(date: Any = None) -> pd.DataFrame:


    if date is not None and str(date).strip():
        _to_date(date)

    text, source_url, date_header = _download_chinamoney_realtime_page()
    observation_date = _guess_observation_date(date_header)
    errors: list[str] = []

    try:
        tables = pd.read_html(StringIO(text))
    except Exception as exc:
        tables = []
        errors.append(f"read_html: {exc}")

    for table in tables:
        try:
            curve = _parse_chinamoney_realtime_table(
                table,
                observation_date=observation_date,
                source_url=source_url,
            )
            if not curve.empty:
                return curve.sort_values("period").reset_index(drop=True)
        except Exception as exc:
            errors.append(str(exc))

    try:
        curve = _parse_chinamoney_realtime_text(
            text,
            observation_date=observation_date,
            source_url=source_url,
        )
        if not curve.empty:
            return curve.sort_values("period").reset_index(drop=True)
    except Exception as exc:
        errors.append(str(exc))

    raise ValueError(
        "Не удалось распознать CNY-кривую на ChinaMoney. "
        "Последние ошибки: " + " | ".join(errors[-5:])
    )


def get_external_curve(currency: str, date: Any) -> pd.DataFrame:
    currency = _clean_text(currency).upper()
    if currency == "USD":
        return get_us_treasury_curve(date)
    if currency == "CNY":
        return get_chinamoney_cny_curve(date)
    raise ValueError("Поддерживаются только USD и CNY")


def discount_factor_from_rate(rate_percent: float, T: float, *, compounding: str = "continuous") -> float:

    r = float(rate_percent) / 100.0
    T = float(T)
    if T < 0:
        raise ValueError("T должен быть >= 0")
    c = str(compounding).strip().lower()
    if c.startswith("annual") or c.startswith("simple"):
        return float(1.0 / ((1.0 + r) ** T))
    return float(np.exp(-r * T))


def interpolate_rate(curve_df: pd.DataFrame, T: float) -> float:
    if curve_df is None or curve_df.empty:
        raise ValueError("Кривая пустая")
    df = curve_df.copy()
    df["period"] = pd.to_numeric(df["period"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).eq("OK") | ~df["Status"].astype(str).str.startswith("ERROR")]
    df = df.dropna(subset=["period", "value"]).sort_values("period")
    if df.empty:
        raise ValueError("В кривой нет числовых period/value")
    return float(np.interp(float(T), df["period"].to_numpy(dtype=float), df["value"].to_numpy(dtype=float)))


def discount_factors_from_curve(curve_df: pd.DataFrame, T: float, *, compounding: str = "continuous") -> dict[str, float]:
    rate = interpolate_rate(curve_df, T)
    df = discount_factor_from_rate(rate, T, compounding=compounding)
    return {
        "T": float(T),
        "Rate Percent": float(rate),
        "Discount Factor": float(df),
        "Growth Factor": float(1.0 / df if df != 0 else np.nan),
    }


def years_between(start_date: Any, end_date: Any) -> float:
    start = _to_date(start_date)
    end = _to_date(end_date)
    return float((end - start) / pd.Timedelta(days=365))
