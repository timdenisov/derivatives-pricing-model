import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import scipy as sc
from datetime import datetime, timedelta
import requests


from typing import List, Tuple, Optional


date_now = None
date_executed = pd.Timestamp("2026-11-03")

if date_now is None:
    date_now = pd.Timestamp.today()
else:
    date_now = pd.Timestamp(date_now)


div_dates = [pd.Timestamp("2025-11-29")]
div_amount = [0]


derivative_type = "Option"
S =  62.16
K = 60
T = (date_executed-date_now)/pd.Timedelta(days=365)
Rd = 0.0425
Rf = 0.025
Sig = 0.23809
q = 0
option_type_country = "American"
Underl_Asset = "Index"
Option_type = "Call"
N_sim = 5000
seed = 42
N_steps = 100
Poly_degree= 3

notional = 1000000
freq = 4


cost_of_carry = 0.0
storage_payments = []

y = 0.0


class Swap_IRS:
    def __init__(self, T, freq, notional, date):
        self.T = T
        self.freq = freq
        self.N = notional
        self.date = date

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

        return df

    def _load_curve(self):
        base_date = datetime.strptime(self.date, "%Y-%m-%d")

        for i in range(3):
            test_date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")

            df = self._fetch_curve(test_date)

            if not df.empty:


                curve = df[["period", "value"]].copy()
                curve["value"] = curve["value"] / 100
                return curve

        raise ValueError("Не удалось загрузить кривую (нет данных за последние 3 дня)")

    def _get_rate(self, t):
        return np.interp(t, self.curve["period"], self.curve["value"])

    def _df(self, t):
        r = self._get_rate(t)
        return np.exp(-r * t)

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


    def price(self):
        times = self._payment_times()

        pv_float = self.N * (1 - self._df(self.T))

        annuity = 0.0
        prev_t = 0.0

        for t in times:
            accrual = t - prev_t
            annuity += self._df(t) * accrual
            prev_t = t

        fixed_rate = pv_float / (self.N * annuity)

        return fixed_rate


class EUR_S_EQ_option:
    def __init__(self, S, K, T, Rd, Sig, q, Option_type, N_sim, seed):
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Sig=Sig
        self.q= q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim=N_sim


        self.d1 = (np.log(self.S/self.K)+(self.Rd -self.q+self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.d2 = (np.log(self.S/self.K)+(self.Rd-self.q-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)

        self.Nd1m = sc.stats.norm.cdf(-self.d1)


        self.Nd2 = sc.stats.norm.cdf(self.d2)

        self.Nd2m = sc.stats.norm.cdf(-self.d2)


    def Call_price(self):
        return self.S*np.exp(-self.q*self.T)*self.Nd1 - self.K*np.exp(-self.Rd*self.T)*self.Nd2

    def Put_price(self):
        return self.K*np.exp(-self.Rd*self.T)*self.Nd2m-self.S*np.exp(-self.q*self.T)*self.Nd1m

    def Monte_carlo_sim(self):
        rng = np.random.default_rng(self.seed)

        Z = rng.standard_normal(self.N_sim)
        S_T = self.S*np.exp((self.Rd -self.q- 0.5*self.Sig**2)*self.T + self.Sig*np.sqrt(self.T)*Z)


        if self.Option_type.lower() == "call":
            payoffs =np.maximum(S_T-self.K,0)
        else:
            payoffs = np.maximum(self.K-S_T,0)


        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price


class EUR_S_IND_option:
    def __init__(self, S, K, T, Rd, Sig, q, Option_type, N_sim, seed):
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Sig=Sig
        self.q = q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim=N_sim


        self.d1 = (np.log(self.S/self.K)+(self.Rd-self.q+self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.d2 = (np.log(self.S/self.K)+(self.Rd-self.q-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)

        self.Nd1m = sc.stats.norm.cdf(-self.d1)


        self.Nd2 = sc.stats.norm.cdf(self.d2)

        self.Nd2m = sc.stats.norm.cdf(-self.d2)


    def Call_price(self):
        return self.S*np.exp(self.q*self.T)*self.Nd1 - self.K*np.exp(-self.Rd*self.T)*self.Nd2

    def Put_price(self):
        return self.K*np.exp(-self.Rd*self.T)*self.Nd2m-self.S*np.exp(self.q*self.T)*self.Nd1m

    def Monte_carlo_sim(self):
        rng = np.random.default_rng(self.seed)

        Z = rng.standard_normal(self.N_sim)
        S_T = self.S*np.exp((self.Rd - self.q - 0.5*self.Sig**2)*self.T + self.Sig*np.sqrt(self.T)*Z)


        if self.Option_type.lower() == "call":
            payoffs =np.maximum(S_T-self.K,0)
        else:
            payoffs = np.maximum(self.K-S_T,0)


        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price


class EUR_F_FX_option:
    def __init__(self, S, K, T, Rd, Rf, Sig, q, Option_type, N_sim, seed):
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Rf = Rf
        self.Sig=Sig
        self.q = q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim=N_sim


        self.F0 = self.S * np.exp((self.Rd - self.Rf) * self.T)

        self.d1 = (np.log(self.S/self.K)+(self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.d2 = (np.log(self.S/self.K)+(-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)

        self.Nd1m = sc.stats.norm.cdf(-self.d1)


        self.Nd2 = sc.stats.norm.cdf(self.d2)

        self.Nd2m = sc.stats.norm.cdf(-self.d2)


    def Call_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd1-self.K*self.Nd2)

    def Put_price(self):
        return np.exp(-self.Rd*self.T)*(self.K*self.Nd2m-self.S*self.Nd1m)

    def Monte_carlo_sim(self):
        rng = np.random.default_rng(self.seed)

        Z = rng.standard_normal(self.N_sim)
        F_T = self.S*np.exp((-0.5*self.Sig**2)*self.T + self.Sig*np.sqrt(self.T)*Z)


        if self.Option_type.lower() == "call":
            payoffs =np.maximum(F_T-self.K,0)
        else:
            payoffs = np.maximum(self.K-F_T,0)


        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price


class EUR_F_Commodity_option:
    def __init__(self, S, K, T, Rd, Rf, Sig, q, Option_type, N_sim, seed):
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Rf = Rf
        self.Sig=Sig
        self.q = q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim=N_sim


        self.F0 = self.S * np.exp((self.Rd - self.Rf) * self.T)

        self.d1 = (np.log(self.S/self.K)+(self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.d2 = (np.log(self.S/self.K)+(-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)

        self.Nd1m = sc.stats.norm.cdf(-self.d1)


        self.Nd2 = sc.stats.norm.cdf(self.d2)

        self.Nd2m = sc.stats.norm.cdf(-self.d2)


    def Call_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd1-self.K*self.Nd2)

    def Put_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd2m-self.S*self.Nd1m)

    def Monte_carlo_sim(self):
        rng = np.random.default_rng(self.seed)

        Z = rng.standard_normal(self.N_sim)
        F_T = self.S*np.exp((-0.5*self.Sig**2)*self.T + self.Sig*np.sqrt(self.T)*Z)


        if self.Option_type.lower() == "call":
            payoffs =np.maximum(F_T-self.K,0)
        else:
            payoffs = np.maximum(self.K-F_T,0)


        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price


class US_S_EQ_option:
    def __init__(self, S, K, T, Rd, Sig, q, Option_type, N_sim, N_steps, Poly_degree,
                 div_dates=None, div_amounts=None, date_now=None, seed=None):
        self.S0 = S
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Sig = Sig
        self.Q = q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim = N_sim
        self.N_steps = N_steps
        self.Poly_degree = Poly_degree

        self.Step = self.T / self.N_steps
        self.Disc = np.exp(-self.Rd * self.Step)
        self.U = np.exp(self.Sig * np.sqrt(self.Step))
        self.D = 1 / self.U
        self.P = (np.exp((self.Rd - self.Q) * self.Step) - self.D) / (self.U - self.D)

        self.div_date = div_dates if div_dates is not None else []
        self.div_amount = div_amounts if div_amounts is not None else []
        self.date_now = date_now

        self.dividend_map = {}
        if self.date_now is not None:
            for div_date, div_amount in zip(self.div_date, self.div_amount):
                if self.date_now <= div_date <= self.date_now + pd.Timedelta(days=int(self.T * 365)):
                    t_div = (div_date - self.date_now) / pd.Timedelta(days=365)
                    step = int(round(t_div * self.N_steps))
                    if 0 < step <= self.N_steps:
                        self.dividend_map[step] = self.dividend_map.get(step, 0.0) + div_amount

        self.adjust_price_for_div()

    def adjust_price_for_div(self):
        if self.dividend_map:
            total_pv = 0.0
            for step, amount in self.dividend_map.items():
                t = step * self.Step
                total_pv += amount * np.exp(-self.Rd * t)
            self.S = max(self.S0 - total_pv, 0.0)

    def price(self):
        J = np.arange(self.N_steps, -1, -1)
        ST = self.S * (self.U ** (self.N_steps - J)) * (self.D ** J)
        if self.Option_type == "Call":
            values = np.maximum(ST - self.K, 0.0)
        else:
            values = np.maximum(self.K - ST, 0.0)

        for i in range(self.N_steps - 1, -1, -1):
            J = np.arange(i, -1, -1)
            Si = self.S * (self.U ** (i - J)) * (self.D ** J)
            Continuation = self.Disc * (self.P * values[0:i + 1] + (1 - self.P) * values[1:i + 2])
            if self.Option_type == "Call":
                Exercise = np.maximum(Si - self.K, 0.0)
            else:
                Exercise = np.maximum(self.K - Si, 0.0)
            values = np.maximum(Exercise, Continuation)

        return float(values[0])

    def price_trinomial(self):
        N = self.N_steps
        dt = self.T / N

        u = np.exp(self.Sig * np.sqrt(3 * dt))
        d = 1.0 / u
        nu = self.Rd - self.Q - 0.5 * self.Sig ** 2
        lam = (nu * np.sqrt(dt)) / (2 * self.Sig * np.sqrt(3)) if self.Sig > 0 else 0.0

        pu = 1.0 / 6.0 + lam
        pd = 1.0 / 6.0 - lam
        pm = 1.0 - pu - pd
        if pm < 0.0:
            pm = 0.0
            total = pu + pd
            if total > 0:
                pu /= total
                pd /= total
        pu = max(0.0, min(1.0, pu))
        pd = max(0.0, min(1.0, pd))
        pm = max(0.0, min(1.0, pm))

        disc = np.exp(-self.Rd * dt)
        ST = self.S * (u ** np.arange(-N, N + 1))
        if self.Option_type == "Call":
            values = np.maximum(ST - self.K, 0.0)
        else:
            values = np.maximum(self.K - ST, 0.0)

        for i in range(N - 1, -1, -1):
            new_values = np.zeros(2 * i + 1)
            for idx, j in enumerate(range(-i, i + 1)):
                center = j + (i + 1)
                cont = disc * (
                    pu * values[center + 1] + pm * values[center] + pd * values[center - 1]
                )
                Si = self.S * (u ** j)
                if self.Option_type == "Call":
                    exercise = max(Si - self.K, 0.0)
                else:
                    exercise = max(self.K - Si, 0.0)
                new_values[idx] = max(exercise, cont)
            values = new_values

        return float(values[0])

    def generate_paths(self):
        rng = np.random.default_rng(self.seed)
        dt = self.T / self.N_steps
        S_paths = np.zeros((self.N_sim, self.N_steps + 1))
        S_paths[:, 0] = self.S0

        for t in range(1, self.N_steps + 1):
            Z = rng.standard_normal(self.N_sim)
            S_paths[:, t] = S_paths[:, t - 1] * np.exp(
                (self.Rd - self.Q - 0.5 * self.Sig ** 2) * dt + self.Sig * np.sqrt(dt) * Z
            )
            if t in self.dividend_map:
                S_paths[:, t] -= self.dividend_map[t]

        return S_paths

    def payoff(self, S):
        if self.Option_type == "Call":
            return np.maximum(S - self.K, 0)
        else:
            return np.maximum(self.K - S, 0)

    def Monte_carlo_sim(self):
        S_paths = self.generate_paths()
        dt = self.T / self.N_steps
        disc = np.exp(-self.Rd * dt)
        V = self.payoff(S_paths[:, -1])

        for t in range(self.N_steps - 1, -1, -1):
            St = S_paths[:, t]
            exercise = self.payoff(St)
            discounted_future = V * disc

            itm = exercise > 0.0
            if np.sum(itm) >= self.Poly_degree + 1:
                X = St[itm]
                Y = discounted_future[itm]
                coeffs = np.polyfit(X, Y, self.Poly_degree)
                continuation = np.polyval(coeffs, St)
            else:
                continuation = np.full_like(exercise, np.mean(discounted_future))

            should_exercise = itm & (exercise > continuation)
            V = np.where(should_exercise, exercise, discounted_future)

        return np.mean(V)


def calc_greeks(
    option_class,
    S, K, T, Rd, Sig,
    q=0.0,
    Rf=0.0,
    Option_type="Call",
    N_sim=10000,
    seed=42,

    N_steps=None,
    Poly_degree=None,
    div_dates=None,
    div_amounts=None,
    date_now=None,
    use_monte_carlo=False,

    h=0.01,
    dt=1/365,
    dr=0.0001
):


    def make_opt(S_=S, T_=T, Rd_=Rd, Sig_=Sig):
        if option_class == US_S_EQ_option:
            return option_class(
                S=S_,
                K=K,
                T=T_,
                Rd=Rd_,
                Sig=Sig_,
                q=q,
                Option_type=Option_type,
                N_sim=N_sim,
                N_steps=N_steps,
                Poly_degree=Poly_degree,
                div_dates=div_dates,
                div_amounts=div_amounts,
                date_now=date_now,
                seed=seed
            )
        elif option_class == EUR_F_FX_option:
            return option_class(
                S=S_,
                K=K,
                T=T_,
                Rd=Rd_,
                Rf=Rf,
                Sig=Sig_,
                q=q,
                Option_type=Option_type,
                N_sim=N_sim,
                seed=seed
            )
        else:
            return option_class(
                S=S_,
                K=K,
                T=T_,
                Rd=Rd_,
                Sig=Sig_,
                q=q,
                Option_type=Option_type,
                N_sim=N_sim,
                seed=seed
            )


    def get_price(opt):
        if use_monte_carlo and hasattr(opt, "Monte_carlo_sim"):
            return opt.Monte_carlo_sim()
        if hasattr(opt, "Call_price") or hasattr(opt, "Put_price"):
            return opt.Call_price() if Option_type == "Call" else opt.Put_price()
        elif hasattr(opt, "price"):
            return opt.price()
        elif hasattr(opt, "Monte_carlo_sim"):
            return opt.Monte_carlo_sim()
        else:
            raise ValueError("Объект не имеет метода расчёта цены.")


    opt = make_opt()
    price = get_price(opt)


    opt_up = make_opt(S_=S + h)
    opt_down = make_opt(S_=S - h)

    price_up = get_price(opt_up)
    price_down = get_price(opt_down)

    delta = (price_up - price_down) / (2 * h)
    gamma = (price_up - 2 * price + price_down) / (h ** 2)


    opt_vega = make_opt(Sig_=Sig + h)
    price_vega = get_price(opt_vega)
    vega = (price_vega - price) / h


    if T > dt:
        opt_theta = make_opt(T_=T - dt)
        price_theta = get_price(opt_theta)
        theta = (price_theta - price) / dt
    else:
        theta = float("nan")


    opt_rho = make_opt(Rd_=Rd + dr)
    price_rho = get_price(opt_rho)
    rho = (price_rho - price) / dr


    return {
        "Price": price,
        "Delta": delta,
        "Gamma": gamma,
        "Vega": vega,
        "Theta": theta,
        "Rho": rho
    }


class S_EQ_fwd:
    def __init__(self, S, T, Rd, q):
        self.S = S
        self.T = T
        self.Rd = Rd
        self.Q= q
    def forward_price(self):
        return self.S*np.exp((self.Rd-self.Q)*self.T)


class S_FX_fwd:
    def __init__(self, S, T, Rd, Rf):
        self.S = S
        self.T = T
        self.Rd = Rd
        self.Rf= Rf
    def forward_price(self):
        return self.S *np.exp((self.Rd-self.Rf)*self.T)


class S_Commodity_fwd:
    def __init__(
        self,
        S,
        T,
        Rd,
        u,
        y,
        date_now,
        storage_payments: Optional[List[Tuple[pd.Timestamp, float]]] = None
        ):
        self.S = S
        self.T = T
        self.Rd = Rd
        self.u= cost_of_carry
        self.y = y
        self.storage_payments =storage_payments if storage_payments else []
        self.date_now = date_now
    def forward_price(self):

        F_cont = self.S*np.exp((self.Rd+self.u-self.y)*self.T)


        extra = 0.0
        for pay_date, amount in self.storage_payments:
            pay_date = pd.Timestamp(pay_date)
            if self.date_now <= pay_date <= self.date_now + pd.Timedelta(days = int(self.T*365+1)):
                t_j = (pay_date -self.date_now)/ pd.Timedelta(days=365)
                extra += amount * np.exp(self.Rd*(self.T -t_j))

        return F_cont+extra


def run_demo():

    if derivative_type == "Option":
        if option_type_country == "European":
            if Underl_Asset == "Equity" or Underl_Asset == "Index":
                option_price = EUR_S_EQ_option(
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Sig=Sig,
                    q=q,
                    Option_type=Option_type,
                    N_sim=N_sim,
                    seed=seed
                )
            if Underl_Asset == "FX" or Underl_Asset == "Commodity":
                option_price = EUR_F_FX_option(
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Rf=Rf,
                    Sig=Sig,
                    q=q,
                    Option_type=Option_type,
                    N_sim=N_sim,
                    seed=seed
                )

        if option_type_country == "American":
            if Underl_Asset == "FX" or Underl_Asset == "Commodity":
                option_price = EUR_F_FX_option(
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Rf=Rf,
                    Sig=Sig,
                    q=q,
                    Option_type=Option_type,
                    N_sim=N_sim,
                    seed=seed
                )

            if Underl_Asset == "Equity" or Underl_Asset == "Index":
                option_price = US_S_EQ_option(
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Sig=Sig,
                    q=q,
                    Option_type=Option_type,
                    N_sim=N_sim,
                    div_dates=div_dates,
                    div_amounts=div_amount,
                    date_now=date_now,
                    seed=seed,
                    N_steps=N_steps,
                    Poly_degree=Poly_degree
                )
    if derivative_type == "Forward":
        if Underl_Asset == "FX":
            forward_price = S_FX_fwd(
                S=S,
                T=T,
                Rd=Rd,
                Rf=Rf
            )

        if Underl_Asset in ("Index", "Equity"):
            forward_price = S_FX_fwd(
                S=S,
                T=T,
                Rd=Rd,
                Rf=Rf
            )
        if Underl_Asset == "Commodity":
            forward_price = S_Commodity_fwd(
                S=S,
                T=T,
                Rd=Rd,
                u=cost_of_carry,
                y=y,
                storage_payments=storage_payments,
                date_now=date_now
            )


    if derivative_type == "Option":
        if option_type_country == "European":
            print(f"Option ({Underl_Asset}, European, {Option_type}) price:")
            analytical_price = option_price.Call_price() if Option_type == "Call" else option_price.Put_price()
            print(f"Analytical: {analytical_price:.4f}")
            price_mc = option_price.Monte_carlo_sim()
            print(f"Monte Carlo: {price_mc:.4f}")

            greeks = calc_greeks(
                option_class=EUR_S_EQ_option if Underl_Asset in ("Equity", "Index") else EUR_F_FX_option,
                S=S, K=K, T=T, Rd=Rd, Sig=Sig, q=q, Option_type=Option_type, N_sim=N_sim, seed=seed
            )

            print("\nGreeks:")
            for g, val in greeks.items():
                print(f"{g}: {val:.6f}")

        if option_type_country == "American":
            print(f"Option ({Underl_Asset}, American, {Option_type}) price:")
            binomial_price = option_price.price()
            print(f"Binomial/Regression: {binomial_price:.4f}")
            price_mc = option_price.Monte_carlo_sim()
            print(f"Monte Carlo: {price_mc:.4f}")

            greeks = calc_greeks(
                option_class=US_S_EQ_option,
                S=S,
                K=K,
                T=T,
                Rd=Rd,
                Sig=Sig,
                q=q,
                Option_type=Option_type,
                N_sim=N_sim,
                seed=seed,
                N_steps=N_steps,
                Poly_degree=Poly_degree,
                div_dates=div_dates,
                div_amounts=div_amount,
                date_now=date_now
            )

            print("\nGreeks:")
            for g, val in greeks.items():
                print(f"{g}: {val:.6f}")

    if derivative_type == "Forward":
        print(f"forward on {Underl_Asset},  price")
        print(f"Analytical: {forward_price.forward_price():.4f}")


if __name__ == "__main__":
    run_demo()
