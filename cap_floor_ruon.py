import requests
import pandas as pd
import numpy as np
from math import exp, log, sqrt, erf, pi
from datetime import datetime, timedelta


"""
код для запуска:


cap = CapFloor_RUONIA(
    option_type="put",
    notional=100_000_000,
    strike=0.12,       # 13%
    maturity=2.5,
    freq=4,
    vol=0.015,         # normal vol для Bachelier
    spot_rate=0.15,   # текущая ставка 12.5%
    date="2026-04-19",
    model="bachelier"
)

price, details = cap.price()

print("Цена cap:", price)


print(details)

"""


class CapFloor_RUONIA:
    def __init__(self, option_type, notional, strike, maturity, freq,
                 vol, spot_rate, date, model="bachelier"):
        """
        option_type : 'cap' или 'floor'
        notional    : номинал
        strike      : страйк в долях, например 0.13
        maturity    : срок в годах, например 2 или 2.5
        freq        : частота платежей, например 4
        vol         : волатильность, вводится вручную
        spot_rate   : текущая spot-ставка, вводится вручную, в долях
        date        : дата zero curve, YYYY-MM-DD
        model       : 'bachelier' или 'black'
        """
        self.option_type = option_type.lower()
        self.N = notional
        self.K = strike
        self.T = maturity
        self.freq = freq
        self.vol = vol
        self.spot_rate = spot_rate
        self.date = date
        self.model = model.lower()

        self.curve = self._load_curve()

    def _fetch_curve(self, date_str):
        url = "https://iss.moex.com/iss/engines/stock/zcyc/yearyields.json"
        params = {"date": date_str}

        r = requests.get(url, params=params, timeout=30)
        data = r.json()

        if "yearyields" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(
            data["yearyields"]["data"],
            columns=data["yearyields"]["columns"]
        )

        if df.empty:
            return pd.DataFrame()

        df = df[["period", "value"]].copy()
        df["period"] = pd.to_numeric(df["period"])
        df["value"] = pd.to_numeric(df["value"]) / 100.0

        return df

    def _load_curve(self):
        base_date = datetime.strptime(self.date, "%Y-%m-%d")

        for i in range(3):
            d = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
            df = self._fetch_curve(d)

            if not df.empty:
                print(f"Используем дату zero curve: {d}")
                return df

        raise ValueError("Не удалось загрузить zero curve за последние 3 дня")

    def _get_rate(self, t):
        return np.interp(t, self.curve["period"], self.curve["value"])

    def _df(self, t):
        r = self._get_rate(t)
        return exp(-r * t)

    def _forward_rate(self, t1, t2):
        df1 = self._df(t1)
        df2 = self._df(t2)
        tau = t2 - t1
        return (df1 / df2 - 1.0) / tau

    def _payment_times(self):
        step = 1 / self.freq
        times = []
        t = step

        while t < self.T:
            times.append(round(t, 10))
            t += step

        if not times or times[-1] != self.T:
            times.append(self.T)

        return np.array(times)

    def _norm_cdf(self, x):
        return 0.5 * (1.0 + erf(x / sqrt(2.0)))

    def _norm_pdf(self, x):
        return (1.0 / sqrt(2.0 * pi)) * exp(-0.5 * x * x)

    def _optionlet_bachelier(self, F, K, sigma, tau_reset, tau_pay, df_pay):
        std = sigma * sqrt(max(tau_reset, 1e-12))

        if std < 1e-14:
            if self.option_type == "cap":
                intrinsic = max(F - K, 0.0)
            else:
                intrinsic = max(K - F, 0.0)
            return self.N * tau_pay * df_pay * intrinsic

        d = (F - K) / std

        if self.option_type == "cap":
            value = (F - K) * self._norm_cdf(d) + std * self._norm_pdf(d)
        else:
            value = (K - F) * self._norm_cdf(-d) + std * self._norm_pdf(d)

        return self.N * tau_pay * df_pay * value

    def _optionlet_black(self, F, K, sigma, tau_reset, tau_pay, df_pay):
        if F <= 0 or K <= 0:
            raise ValueError("Для Black-модели F и K должны быть > 0")

        vol_sqrt_t = sigma * sqrt(max(tau_reset, 1e-12))

        if vol_sqrt_t < 1e-14:
            if self.option_type == "cap":
                intrinsic = max(F - K, 0.0)
            else:
                intrinsic = max(K - F, 0.0)
            return self.N * tau_pay * df_pay * intrinsic

        d1 = (log(F / K) + 0.5 * sigma * sigma * tau_reset) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t

        if self.option_type == "cap":
            value = F * self._norm_cdf(d1) - K * self._norm_cdf(d2)
        else:
            value = K * self._norm_cdf(-d2) - F * self._norm_cdf(-d1)

        return self.N * tau_pay * df_pay * value

    def price(self):
        times = self._payment_times()

        pv = 0.0
        details = []
        prev_t = 0.0

        for i, t in enumerate(times):
            tau_pay = t - prev_t
            df_pay = self._df(t)

            # Первый период — используем известную текущую spot-ставку
            # Остальные периоды — форвард из zero curve
            if i == 0:
                rate_used = self.spot_rate
                rate_type = "spot"
            else:
                rate_used = self._forward_rate(prev_t, t)
                rate_type = "forward"

            tau_reset = prev_t

            if self.model == "bachelier":
                pvlet = self._optionlet_bachelier(
                    F=rate_used,
                    K=self.K,
                    sigma=self.vol,
                    tau_reset=tau_reset,
                    tau_pay=tau_pay,
                    df_pay=df_pay
                )
            elif self.model == "black":
                pvlet = self._optionlet_black(
                    F=rate_used,
                    K=self.K,
                    sigma=self.vol,
                    tau_reset=tau_reset,
                    tau_pay=tau_pay,
                    df_pay=df_pay
                )
            else:
                raise ValueError("model должен быть 'bachelier' или 'black'")

            details.append({
                "start": prev_t,
                "end": t,
                "tau": tau_pay,
                "rate_type": rate_type,
                "rate_used": rate_used,
                "df": df_pay,
                "pvlet": pvlet
            })

            pv += pvlet
            prev_t = t

        return pv, pd.DataFrame(details)