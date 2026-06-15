from __future__ import annotations


import sys
import subprocess
import importlib.util

REQUIRED_PACKAGES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "requests": "requests",
    "seaborn": "seaborn",
    "matplotlib": "matplotlib",
    "plotly": "plotly",
    "kaleido": "kaleido",
    "mplcursors": "mplcursors",
    "openpyxl": "openpyxl",
}

def install_and_import_packages():
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(import_name) is None:
            print(f"Библиотека {pip_name} не найдена. Устанавливаю...")
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                pip_name
            ])

install_and_import_packages()


from pathlib import Path
from datetime import datetime
import traceback
import tempfile
import webbrowser

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
try:
    import mplcursors
except Exception:
    mplcursors = None

import pandas as pd
import numpy as np
import plotly.graph_objects as go

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog


BASE_DIR = Path(__file__).parent


PRICING_FILE = "pricing__2_.py"
ZCYC_FILE    = "zcyc_построить_на_конкретный_день.py"
CAP_FILE     = "cap_floor_ruon.py"
VOL_FILE     = "vol_surface.py"
STRATEGY_FILE = "option_strategy.py"
MARKET_FILE   = "market_chain.py"
RATES_FILE    = "rates_curves.py"


def _load_module(filename: str, alias: str):

    full_path = BASE_DIR / filename
    if not full_path.exists():
        raise FileNotFoundError(
            f"Не найден файл '{full_path}'. "
            f"Положи его рядом с pricing_gui.py или поправь константу в начале файла."
        )
    spec = importlib.util.spec_from_file_location(alias, full_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


_import_error = None
pricing = zcyc = capf = volsurf = strat = marketchain = ratescurves = None
try:
    pricing = _load_module(PRICING_FILE, "pricing_src")
    zcyc    = _load_module(ZCYC_FILE,    "zcyc_src")
    capf    = _load_module(CAP_FILE,     "capfloor_src")
    volsurf = _load_module(VOL_FILE,     "volsurface_src")
    strat   = _load_module(STRATEGY_FILE, "option_strategy_src")
    marketchain = _load_module(MARKET_FILE, "market_chain_src")
    ratescurves = _load_module(RATES_FILE, "rates_curves_src")
except Exception as e:
    _import_error = e


def parse_float(s: str, name: str) -> float:
    s = s.strip().replace(",", ".")
    if s == "":
        raise ValueError(f"Поле '{name}' пустое")
    return float(s)


def parse_int(s: str, name: str) -> int:
    s = s.strip()
    if s == "":
        raise ValueError(f"Поле '{name}' пустое")
    return int(s)


def parse_optional_int(s: str, name: str) -> int | None:
    s = s.strip()
    if s == "":
        return None
    return int(s)


def parse_date(s: str, name: str) -> pd.Timestamp:
    s = s.strip()
    if s == "":
        raise ValueError(f"Поле '{name}' пустое")

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    raise ValueError(f"Поле '{name}' не в формате YYYY-MM-DD: {s!r}")

def parse_percentage(s: str, name: str) -> float:
    s = s.strip().replace(",", ".")
    if s == "":
        raise ValueError(f"Поле '{name}' пустое")
    return float(s) / 100.0


def parse_list(s: str):

    s = s.strip()
    if s == "":
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def years_between(d_now: pd.Timestamp, d_exp: pd.Timestamp) -> float:
    return (d_exp - d_now) / pd.Timedelta(days=365)


class LabeledEntry:

    def __init__(self, parent, row, label, default="", width=18, hint=""):
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", padx=4, pady=2)
        self.var = tk.StringVar(value=str(default))
        self.entry = ttk.Entry(parent, textvariable=self.var, width=width)
        self.entry.grid(row=row, column=1, sticky="we", padx=4, pady=2)

        self.entry.bind("<Control-c>", self._on_copy)
        self.entry.bind("<Control-C>", self._on_copy)
        self.entry.bind("<Control-v>", self._on_paste)
        self.entry.bind("<Control-V>", self._on_paste)
        self.entry.bind("<Shift-Insert>", self._on_paste)
        if hint:
            hint_lbl = ttk.Label(parent, text=hint, foreground="#777")
            hint_lbl.grid(row=row, column=2, sticky="w", padx=4, pady=2)

    def get(self): return self.var.get()
    def set(self, value): self.var.set(str(value))

    def _on_copy(self, event):
        try:
            sel_start = self.entry.index("sel.first")
            sel_end = self.entry.index("sel.last")
            txt = self.entry.get()[int(sel_start):int(sel_end)]
            self.entry.clipboard_clear()
            self.entry.clipboard_append(txt)
        except tk.TclError:
            pass
        return "break"

    def _on_paste(self, event):
        try:
            txt = self.entry.clipboard_get()
            self.entry.delete(0, tk.END)
            self.entry.insert(0, txt)
        except tk.TclError:
            pass
        return "break"


class LabeledCombo:
    def __init__(self, parent, row, label, values, default=None, width=16, on_change=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
        self.var = tk.StringVar(value=default if default is not None else values[0])
        self.combo = ttk.Combobox(parent, textvariable=self.var, values=values,
                                  state="readonly", width=width)
        self.combo.grid(row=row, column=1, sticky="we", padx=4, pady=2)
        if on_change is not None:
            self.combo.bind("<<ComboboxSelected>>", lambda e: on_change())

    def get(self): return self.var.get()
    def set(self, value): self.var.set(value)


def make_result_box(parent):
    box = scrolledtext.ScrolledText(parent, height=14, width=80,
                                    font=("Consolas", 10), wrap="word")
    box.configure(state="disabled")
    return box


def write_result(box, text, append=False):
    box.configure(state="normal")
    if not append:
        box.delete("1.0", tk.END)
    box.insert(tk.END, text)
    box.see(tk.END)
    box.configure(state="disabled")


def show_error(title, exc):
    tb = traceback.format_exc()
    messagebox.showerror(title, f"{exc}\n\n{tb}")


def open_plotly_figure(fig, filename_prefix: str, output_format: str = "HTML") -> Path:

    charts_dir = BASE_DIR / "interactive_charts"
    charts_dir.mkdir(exist_ok=True)
    safe_prefix = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in filename_prefix)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    fmt = (output_format or "HTML").upper()
    if fmt == "PNG":
        path = charts_dir / f"{safe_prefix}_{stamp}.png"

        fig.write_image(str(path), width=1300, height=850, scale=2)
    else:
        path = charts_dir / f"{safe_prefix}_{stamp}.html"
        fig.write_html(str(path), include_plotlyjs=True, full_html=True, auto_open=False)

    webbrowser.open_new_tab(path.resolve().as_uri())
    return path


def add_mpl_hover(artist, labels):

    if mplcursors is None:
        return None
    cursor = mplcursors.cursor(artist, hover=True)

    @cursor.connect("add")
    def _on_add(sel):
        try:
            idx = int(sel.index)
            if 0 <= idx < len(labels):
                sel.annotation.set_text(labels[idx])
        except Exception:
            pass

    return cursor


ACTION_BUTTON_GREEN = {
    "bg": "#28a745",
    "fg": "white",
    "activebackground": "#218838",
    "activeforeground": "white",
}
ACTION_BUTTON_DONE = {
    "bg": "#E0E0E0",
    "fg": "black",
    "activebackground": "#D5D5D5",
    "activeforeground": "black",
}

def set_action_button_state(button, pending: bool = True):

    try:
        button.configure(**(ACTION_BUTTON_GREEN if pending else ACTION_BUTTON_DONE))
    except tk.TclError:
        pass


class OptionsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)


        top = ttk.LabelFrame(self, text="Тип опциона")
        top.pack(fill="x", padx=4, pady=4)

        self.style_cb = LabeledCombo(top, 0, "Стиль:",
            ["European", "American"], default="European", on_change=self._update_fields)
        self.asset_cb = LabeledCombo(top, 1, "Базовый актив:",
            ["Equity", "Index", "FX", "Commodity"], default="Equity", on_change=self._update_fields)
        self.cp_cb = LabeledCombo(top, 2, "Call/Put:",
            ["Call", "Put"], default="Call")


        params = ttk.LabelFrame(self, text="Параметры")
        params.pack(fill="x", padx=4, pady=4)
        params.columnconfigure(1, weight=1)

        self.S  = LabeledEntry(params, 0, "Spot (Цена Спот):",        default="100.00")
        self.K  = LabeledEntry(params, 1, "K (Страйк):",       default="90")
        self.dn = LabeledEntry(params, 2, "Дата оценки:",     default=datetime.today().strftime("%Y-%m-%d"), hint="YYYY-MM-DD")
        self.de = LabeledEntry(params, 3, "Дата экспирации:", default="2026-11-03",                          hint="YYYY-MM-DD")
        self.Rd = LabeledEntry(params, 4, "Rd (безрисковая ставка в валюте котирования):", default="0.0425")
        self.Rf = LabeledEntry(params, 5, "Rf (ставка в смежной валюте):",       default="0.025")
        self.Sig = LabeledEntry(params, 6, "Volatility:",    default="0.23809")
        self.q  = LabeledEntry(params, 7, "Dividend yield (в % годовых):",    default="0.0")


        sim = ttk.LabelFrame(self, text="Симуляции / дерево")
        sim.pack(fill="x", padx=4, pady=4)
        sim.columnconfigure(1, weight=1)

        self.N_sim = LabeledEntry(sim, 0, "N_sim (количество MC траекторий):", default="5000")
        self.N_steps = LabeledEntry(sim, 1, "N_steps (шагов дерева / временных периодов):", default="252")
        self.Poly_degree = LabeledEntry(sim, 2, "Poly_degree (LSM):", default="3")
        self.seed = LabeledEntry(sim, 3, "seed:", default="1")
        ttk.Label(sim, text="N_steps используется для биномиального/триномиального дерева", foreground="#777").grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=2)


        self.div_frame = ttk.LabelFrame(self, text="Дивиденды (только American Equity)")
        self.div_frame.pack(fill="x", padx=4, pady=4)
        self.div_frame.columnconfigure(1, weight=1)

        self.div_dates = LabeledEntry(self.div_frame, 0, "Даты дивидендов (через запятую):",
                                      default="", hint="пример: 2025-11-29, 2026-05-15")
        self.div_amount = LabeledEntry(self.div_frame, 1, "Суммы дивидендов (через запятую):",
                                       default="", hint="пример: 0.5, 0.6")


        ttk.Label(self, text="Для расчета греков отметьте:", foreground="#333").pack(anchor="w", padx=8, pady=(6, 2))
        self.calc_greeks_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Рассчитать греки через триномиальное дерево",
                variable=self.calc_greeks_var).pack(anchor="w", padx=8, pady=2)


        ttk.Button(self, text="Рассчитать", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

        self._update_fields()


    def _update_fields(self):

        style = self.style_cb.get()
        asset = self.asset_cb.get()


        need_rf = asset in ("FX", "Commodity")
        for widget in (self.Rf.entry,):
            widget.configure(state="normal" if need_rf else "disabled")


        if style == "American" and asset in ("Equity", "Index"):
            for child in self.div_frame.winfo_children():
                try: child.configure(state="normal")
                except tk.TclError: pass
        else:
            for child in self.div_frame.winfo_children():
                try: child.configure(state="disabled")
                except tk.TclError: pass


        self.Poly_degree.entry.configure(state="normal" if style == "American" else "disabled")


    def _on_calculate(self):
        try:
            style = self.style_cb.get()
            asset = self.asset_cb.get()
            cp    = self.cp_cb.get()

            S  = parse_float(self.S.get(),  "S")
            K  = parse_float(self.K.get(),  "K")
            dn = parse_date(self.dn.get(),  "date_now")
            de = parse_date(self.de.get(),  "date_executed")
            T  = years_between(dn, de)
            if T <= 0:
                raise ValueError("Дата экспирации должна быть позже даты оценки (T > 0).")

            Rd  = parse_float(self.Rd.get(),  "Rd")
            Rf  = parse_float(self.Rf.get(),  "Rf") if asset in ("FX", "Commodity") else 0.0
            Sig = parse_float(self.Sig.get(), "Sigma")
            q   = parse_percentage(self.q.get(),   "q")

            N_sim   = parse_int(self.N_sim.get(),   "N_sim")
            N_steps = parse_int(self.N_steps.get(), "N_steps")
            Poly_d  = parse_int(self.Poly_degree.get(), "Poly_degree")
            seed    = parse_optional_int(self.seed.get(),    "seed")


            opt = None
            option_class = None

            if style == "European":
                if asset in ("Equity", "Index"):
                    option_class = pricing.EUR_S_EQ_option if asset == "Equity" else pricing.EUR_S_IND_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)
                else:
                    option_class = pricing.EUR_F_FX_option if asset == "FX" else pricing.EUR_F_Commodity_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Rf=Rf, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)

            else:
                if asset in ("Equity", "Index"):

                    dd = [parse_date(d, f"div_date[{i}]")
                          for i, d in enumerate(parse_list(self.div_dates.get()))]
                    da = [float(x.replace(",", "."))
                          for x in parse_list(self.div_amount.get())]
                    if len(dd) != len(da):
                        raise ValueError("Число дат дивидендов и сумм должно совпадать.")

                    option_class = pricing.US_S_EQ_option
                    opt = option_class(
                        S=S, K=K, T=T, Rd=Rd, Sig=Sig, q=q,
                        Option_type=cp, N_sim=N_sim,
                        N_steps=N_steps, Poly_degree=Poly_d,
                        div_dates=dd, div_amounts=da, date_now=dn, seed=seed
                    )
                else:

                    option_class = pricing.EUR_F_FX_option if asset == "FX" else pricing.EUR_F_Commodity_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Rf=Rf, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)


            lines = []
            lines.append(f"Опцион: {asset}, {style}, {cp}")
            lines.append(f"T = {T:.6f} лет")
            lines.append("-" * 60)

            if style == "European":
                price_analytical = opt.Call_price() if cp == "Call" else opt.Put_price()
                lines.append(f"Analytical (закрытая формула):  {price_analytical:.6f}")
                price_mc = opt.Monte_carlo_sim()
                lines.append(f"Monte-Carlo (N={N_sim}):          {price_mc:.6f}")
            else:

                if asset in ("Equity", "Index"):
                    price_bin = opt.price()
                    lines.append(f"Binomial tree:                    {price_bin:.6f}")
                    try:
                        price_tri = opt.price_trinomial()
                    except Exception:
                        price_tri = volsurf.trinomial_tree_price(
                            asset_type=asset, option_style=style, S=S, K=K, T=T, Rd=Rd, Rf=Rf, q=q,
                            sigma=Sig, option_type=cp, n_steps=N_steps,
                        )
                    lines.append(f"Trinomial tree:                   {price_tri:.6f}")
                    price_mc = opt.Monte_carlo_sim()
                    lines.append(f"LSM / Monte-Carlo (N={N_sim}):     {price_mc:.6f}")
                else:
                    price_tri = volsurf.trinomial_tree_price(
                        asset_type=asset, option_style=style, S=S, K=K, T=T, Rd=Rd, Rf=Rf, q=q,
                        sigma=Sig, option_type=cp, n_steps=N_steps,
                    )
                    lines.append(f"Trinomial tree:                   {price_tri:.6f}")


            if self.calc_greeks_var.get():
                lines.append("")
                lines.append("Greeks (Trinomial tree bump-and-reprice):")
                greeks = volsurf.calc_option_greeks_trinomial(
                    asset_type=asset,
                    option_style=style,
                    S=S,
                    K=K,
                    T=T,
                    Rd=Rd,
                    Rf=Rf,
                    q=q,
                    sigma=Sig,
                    option_type=cp,
                    n_steps=N_steps,
                )
                for g, v in greeks.items():
                    if pd.isna(v):
                        lines.append(f"  {g:<7} = nan")
                    elif g == "Price":
                        lines.append(f"  {g:<7} = {v:.6f}")
                    else:
                        lines.append(f"  {g:<7} = {v:.6f}")

            write_result(self.result, "\n".join(lines))

        except Exception as e:
            show_error("Ошибка расчёта опциона", e)


class ForwardsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        top = ttk.LabelFrame(self, text="Тип форварда")
        top.pack(fill="x", padx=4, pady=4)
        self.asset_cb = LabeledCombo(top, 0, "Базовый актив:",
            ["Equity/Index", "FX", "Commodity"], default="Equity/Index",
            on_change=self._update_fields)

        params = ttk.LabelFrame(self, text="Параметры")
        params.pack(fill="x", padx=4, pady=4)
        params.columnconfigure(1, weight=1)

        self.S  = LabeledEntry(params, 0, "S (спот):",            default="100")
        self.dn = LabeledEntry(params, 1, "Дата оценки:",         default=datetime.today().strftime("%Y-%m-%d"),
                               hint="YYYY-MM-DD")
        self.de = LabeledEntry(params, 2, "Дата поставки:",       default="2026-12-31",
                               hint="YYYY-MM-DD")
        self.Rd = LabeledEntry(params, 3, "Rd (risk-free):",       default="0.10")
        self.Rf = LabeledEntry(params, 4, "Rf (для FX):",          default="0.04")
        self.q  = LabeledEntry(params, 5, "q (div yield, Eq/Ind):", default="0.0")

        comm = ttk.LabelFrame(self, text="Только для Commodity")
        comm.pack(fill="x", padx=4, pady=4)
        comm.columnconfigure(1, weight=1)
        self.u = LabeledEntry(comm, 0, "u (cost of carry, непрерывный):", default="0.0")
        self.y = LabeledEntry(comm, 1, "y (convenience yield):",          default="0.0")
        self.storage = LabeledEntry(comm, 2, "Storage payments:", default="",
                                    hint="формат: 2026-03-01=0.5, 2026-06-01=0.3")

        self.comm_frame = comm

        ttk.Button(self, text="Рассчитать форвардную цену", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

        self._update_fields()

    def _update_fields(self):
        asset = self.asset_cb.get()

        self.Rf.entry.configure(state="normal" if asset == "FX" else "disabled")

        self.q.entry.configure(state="normal" if asset == "Equity/Index" else "disabled")

        state = "normal" if asset == "Commodity" else "disabled"
        for child in self.comm_frame.winfo_children():
            try: child.configure(state=state)
            except tk.TclError: pass

    def _on_calculate(self):
        try:
            asset = self.asset_cb.get()
            S  = parse_float(self.S.get(),  "S")
            dn = parse_date(self.dn.get(),  "date_now")
            de = parse_date(self.de.get(),  "date_executed")
            T  = years_between(dn, de)
            if T <= 0:
                raise ValueError("Дата поставки должна быть позже даты оценки.")

            Rd = parse_float(self.Rd.get(), "Rd")

            if asset == "FX":
                Rf = parse_float(self.Rf.get(), "Rf")
                fwd = pricing.S_FX_fwd(S=S, T=T, Rd=Rd, Rf=Rf)
                price = fwd.forward_price()
                text = (f"FX Forward\n"
                        f"S = {S}, T = {T:.6f} лет, Rd = {Rd}, Rf = {Rf}\n"
                        f"Forward price = {price:.6f}")

            elif asset == "Equity/Index":
                q = parse_float(self.q.get(), "q")
                fwd = pricing.S_EQ_fwd(S=S, T=T, Rd=Rd, q=q)
                price = fwd.forward_price()
                text = (f"Equity/Index Forward\n"
                        f"S = {S}, T = {T:.6f} лет, Rd = {Rd}, q = {q}\n"
                        f"Forward price = {price:.6f}")

            else:
                u = parse_float(self.u.get(), "u")
                y = parse_float(self.y.get(), "y")

                storage = []
                raw = self.storage.get().strip()
                if raw:
                    for token in parse_list(raw):
                        if "=" not in token:
                            raise ValueError(f"Неверный формат storage: {token!r}. "
                                             f"Нужно 'YYYY-MM-DD=amount'.")
                        d_str, a_str = token.split("=", 1)
                        d = parse_date(d_str, "storage date")
                        a = float(a_str.strip().replace(",", "."))
                        storage.append((d, a))

                fwd = pricing.S_Commodity_fwd(
                    S=S, T=T, Rd=Rd, u=u, y=y,
                    date_now=dn, storage_payments=storage
                )
                price = fwd.forward_price()
                text = (f"Commodity Forward\n"
                        f"S = {S}, T = {T:.6f} лет, Rd = {Rd}, u = {u}, y = {y}\n"
                        f"Storage payments = {storage if storage else '—'}\n"
                        f"Forward price = {price:.6f}")

            write_result(self.result, text)

        except Exception as e:
            show_error("Ошибка расчёта форварда", e)


class SwapTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        params = ttk.LabelFrame(self, text="Параметры свопа (фиксированная нога против плавающей)")
        params.pack(fill="x", padx=4, pady=4)
        params.columnconfigure(1, weight=1)

        self.T    = LabeledEntry(params, 0, "T (срок, лет):",      default="3")
        self.freq = LabeledEntry(params, 1, "freq (платежей в год):", default="4")
        self.N    = LabeledEntry(params, 2, "Notional:",            default="1000000")
        self.date = LabeledEntry(params, 3, "Дата оценки:", default=datetime.today().strftime("%Y-%m-%d"),
                                 hint="YYYY-MM-DD, кривая берётся с MOEX")

        ttk.Button(self, text="Рассчитать fixed rate", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

    def _on_calculate(self):
        try:
            T    = parse_float(self.T.get(),    "T")
            freq = parse_int(self.freq.get(),   "freq")
            N    = parse_float(self.N.get(),    "Notional")
            date = self.date.get().strip()

            parse_date(date, "date")

            swap = pricing.Swap_IRS(T=T, freq=freq, notional=N, date=date)
            fixed = swap.price()


            times = swap._payment_times()
            lines = [f"Swap IRS (MOEX zero curve, дата = {date})",
                     f"T = {T}, freq = {freq}, notional = {N:,.0f}".replace(",", " "),
                     "-" * 60,
                     f"Fixed rate = {fixed:.6f}  ({fixed*100:.4f} %)",
                     "",
                     "Payment schedule (в годах от оценки):"]
            for t in times:
                r = swap._get_rate(t)
                df = swap._df(t)
                lines.append(f"  t = {t:7.4f}   zero = {r*100:6.3f}%   DF = {df:.6f}")

            write_result(self.result, "\n".join(lines))

        except Exception as e:
            show_error("Ошибка расчёта свопа", e)


class CapFloorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        top = ttk.LabelFrame(self, text="Тип деривата и модель")
        top.pack(fill="x", padx=4, pady=4)

        self.opt_cb = LabeledCombo(top, 0, "Тип:",
            ["cap", "floor"], default="cap")
        self.model_cb = LabeledCombo(top, 1, "Модель:",
            ["bachelier", "black"], default="bachelier")

        params = ttk.LabelFrame(self, text="Параметры")
        params.pack(fill="x", padx=4, pady=4)
        params.columnconfigure(1, weight=1)

        self.N  = LabeledEntry(params, 0, "Notional:",                   default="100000000")
        self.K  = LabeledEntry(params, 1, "Strike (в долях):",            default="0.12",   hint="0.12 = 12%")
        self.T  = LabeledEntry(params, 2, "Maturity (лет):",              default="2.5")
        self.fq = LabeledEntry(params, 3, "freq (платежей в год):",        default="4")
        self.vol = LabeledEntry(params, 4, "Vol:",                         default="0.015",
                                hint="для Bachelier — normal, для Black — lognormal")
        self.spot = LabeledEntry(params, 5, "Spot-ставка сейчас (в долях):", default="0.15", hint="0.15 = 15%")
        self.dt   = LabeledEntry(params, 6, "Дата оценки:",
                                 default=datetime.today().strftime("%Y-%m-%d"),
                                 hint="YYYY-MM-DD, кривая с MOEX")

        ttk.Button(self, text="Рассчитать цену", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

    def _on_calculate(self):
        try:
            opt_type = self.opt_cb.get()
            model    = self.model_cb.get()
            N  = parse_float(self.N.get(),    "Notional")
            K  = parse_float(self.K.get(),    "Strike")
            T  = parse_float(self.T.get(),    "Maturity")
            fq = parse_int(self.fq.get(),     "freq")
            vol = parse_float(self.vol.get(), "Vol")
            spot = parse_float(self.spot.get(), "Spot rate")
            date = self.dt.get().strip()
            parse_date(date, "date")


            cf = capf.CapFloor_RUONIA(
                option_type=opt_type,
                notional=N,
                strike=K,
                maturity=T,
                freq=fq,
                vol=vol,
                spot_rate=spot,
                date=date,
                model=model,
            )
            price, details = cf.price()

            lines = [f"{opt_type.upper()} on RUONIA, model = {model}",
                     f"N = {N:,.0f}  K = {K*100:.3f}%  T = {T}  freq = {fq}".replace(",", " "),
                     f"vol = {vol}   spot = {spot*100:.3f}%   date = {date}",
                     "-" * 70,
                     f"PV = {price:,.2f}".replace(",", " "),
                     "",
                     "Optionlets breakdown:"]
            lines.append(details.to_string(index=False))

            write_result(self.result, "\n".join(lines))

        except Exception as e:
            show_error("Ошибка расчёта cap/floor", e)


class ZCYCTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        controls = ttk.LabelFrame(self, text="MOEX ZCYC RUB - Параметры кривой")
        controls.pack(fill="x", padx=4, pady=4)
        controls.columnconfigure(1, weight=1)

        self.mode_cb = LabeledCombo(
            controls, 0, "Режим:",
            ["single", "week", "month", "year", "custom"],
            default="single",
            on_change=self._update_fields,
        )

        self.base_date = LabeledEntry(
            controls, 1, "base_date (дата кривой):",
            default=datetime.today().strftime("%Y-%m-%d"),
            hint="первая дата ZCYC кривой",
        )
        self.to_date = LabeledEntry(
            controls, 2, "to_date (вторая дата для сравнения):",
            default="",
            hint="только для режима custom",
        )

        graph_controls = ttk.LabelFrame(self, text="График")
        graph_controls.pack(fill="x", padx=4, pady=4)

        ttk.Label(graph_controls, text="Библиотека:").pack(side="left", padx=4)
        self.chart_lib = tk.StringVar(value="Matplotlib (встроенный)")
        ttk.Combobox(
            graph_controls,
            textvariable=self.chart_lib,
            values=["Matplotlib (встроенный)", "Plotly"],
            state="readonly",
            width=22,
        ).pack(side="left", padx=4)

        ttk.Label(graph_controls, text="Plotly output:").pack(side="left", padx=(16, 4))
        self.plotly_output = tk.StringVar(value="HTML")
        ttk.Combobox(
            graph_controls,
            textvariable=self.plotly_output,
            values=["HTML", "PNG"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=4)

        self.plot_curve_button = tk.Button(
            graph_controls,
            text="Построить кривую",
            command=self._on_plot,
            relief="raised",
            padx=10,
            **ACTION_BUTTON_GREEN,
        )
        self.plot_curve_button.pack(side="left", padx=16)

        discount_controls = ttk.LabelFrame(self, text="Discount factor по MOEX ZCYC RUB")
        discount_controls.pack(fill="x", padx=4, pady=4)
        for col in range(8):
            discount_controls.columnconfigure(col, weight=1)

        ttk.Label(discount_controls, text="Cashflow / Target Date:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.df_target_date = tk.StringVar(value="2026-12-31")
        ttk.Entry(discount_controls, textvariable=self.df_target_date, width=14).grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(discount_controls, text="Amount:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.df_amount = tk.StringVar(value="1000000")
        ttk.Entry(discount_controls, textvariable=self.df_amount, width=14).grid(row=0, column=3, sticky="we", padx=4, pady=2)

        ttk.Label(discount_controls, text="Direction:").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.df_direction = tk.StringVar(value="PV: future → today")
        ttk.Combobox(
            discount_controls,
            textvariable=self.df_direction,
            values=["PV: future → today", "FV: today → future"],
            state="readonly",
            width=20,
        ).grid(row=0, column=5, sticky="we", padx=4, pady=2)

        ttk.Button(discount_controls, text="Рассчитать DF", command=self._calculate_discount_factor).grid(row=0, column=6, sticky="we", padx=8, pady=2)
        ttk.Label(
            discount_controls,
            text="DF = exp(-rT), r берётся интерполяцией по MOEX ZCYC на base_date",
            foreground="#777",
        ).grid(row=1, column=0, columnspan=7, sticky="w", padx=4, pady=2)

        self.discount_result = ttk.Label(self, text="", foreground="#333")
        self.discount_result.pack(anchor="w", padx=8, pady=2)

        self.plot_frame = ttk.LabelFrame(self, text="График MOEX ZCYC RUB")
        self.plot_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.fig = Figure(figsize=(9, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self._mpl_cursors = []

        self.info = ttk.Label(self, text="По умолчанию ZCYC RUB строится через Matplotlib прямо в этом окне.", foreground="#555")
        self.info.pack(anchor="w", padx=6, pady=2)

        for entry in (self.base_date.entry, self.to_date.entry):
            entry.bind("<KeyRelease>", self._mark_curve_plot_pending, add="+")
        for var in (self.chart_lib, self.plotly_output):
            try:
                var.trace_add("write", self._mark_curve_plot_pending)
            except Exception:
                pass

        self._update_fields()

    def _update_fields(self):
        mode = self.mode_cb.get()
        is_custom = mode == "custom"
        self.to_date.entry.configure(state="normal" if is_custom else "disabled")
        self._mark_curve_plot_pending()

    def _mark_curve_plot_pending(self, *_):
        if hasattr(self, "plot_curve_button"):
            set_action_button_state(self.plot_curve_button, pending=True)

    def _mark_curve_plot_done(self):
        if hasattr(self, "plot_curve_button"):
            set_action_button_state(self.plot_curve_button, pending=False)

    def _prepare_curves(self):
        mode = self.mode_cb.get()
        loader = zcyc.ZCYCCurveLoader()

        if mode == "custom":
            bd = self.base_date.get().strip()
            to_d = self.to_date.get().strip()
            parse_date(bd, "base_date")
            parse_date(to_d, "to_date")
            dates = loader.get_custom_dates(bd, to_d)
        else:
            bd = self.base_date.get().strip()
            parse_date(bd, "base_date")
            dates = loader.get_predefined_dates(bd, mode)

        curves = loader.get_curves_for_dates(dates, verbose=False)

        if mode == "single":
            title = f"ZCYC на {list(curves.keys())[0]}"
        elif mode == "custom":
            title = f"Сравнение кривых: {self.base_date.get()} vs {self.to_date.get()}"
        else:
            title_map = {
                "week": "Изменение за неделю",
                "month": "Изменение за месяц",
                "year": "Изменение за год",
            }
            title = title_map.get(mode, "ZCYC Curve RUB")
        return curves, title

    def _on_plot(self):
        try:
            curves, title = self._prepare_curves()
            if self.chart_lib.get().startswith("Matplotlib"):
                self._plot_matplotlib(curves, title)
            else:
                self._plot_plotly(curves, title)
            self._mark_curve_plot_done()
        except Exception as e:
            show_error("Ошибка загрузки ZCYC-кривой", e)

    def _calculate_discount_factor(self):
        try:
            curve_date = self.base_date.get().strip()
            target_date = self.df_target_date.get().strip()
            parse_date(curve_date, "base_date")
            parse_date(target_date, "target_date")
            amount = parse_float(self.df_amount.get(), "Amount")

            loader = zcyc.ZCYCCurveLoader()
            curve_df = loader.get_curve(curve_date, verbose=False).sort_values("period").copy()
            T = ratescurves.years_between(curve_date, target_date)
            if T <= 0:
                raise ValueError("Target Date должна быть позже base_date")
            factors = ratescurves.discount_factors_from_curve(curve_df, T, compounding="continuous")
            df = factors["Discount Factor"]
            gf = factors["Growth Factor"]
            rate = factors["Rate Percent"]

            if self.df_direction.get().startswith("PV"):
                result = amount * df
                multiplier = df
                direction_text = "умножить будущую сумму на DF, чтобы получить текущую справедливую стоимость"
            else:
                result = amount * gf
                multiplier = gf
                direction_text = "умножить текущую сумму на Growth Factor, чтобы получить будущую справедливую стоимость"

            self.discount_result.configure(
                text=(
                    f"T={T:.6f} лет | interpolated zero rate={rate:.6f}% | "
                    f"DF={df:.10f} | Growth Factor={gf:.10f} | "
                    f"нужный множитель={multiplier:.10f} | Result={result:,.6f}. "
                    f"Смысл: {direction_text}."
                ).replace(",", " ")
            )
        except Exception as e:
            show_error("Ошибка расчёта discount factor", e)

    def _plot_matplotlib(self, curves, title):
        self.ax.clear()
        self._mpl_cursors = []

        for curve_date, df in curves.items():
            df = df.sort_values("period").copy()
            line, = self.ax.plot(df["period"], df["value"], marker="o", label=str(curve_date))
            labels = [
                f"Дата: {row.tradedate}\n"
                f"Время: {row.tradetime}\n"
                f"Срок: {float(row.period):.4f} лет\n"
                f"Доходность: {float(row.value):.4f}%"
                for row in df.itertuples(index=False)
            ]
            cursor = add_mpl_hover(line, labels)
            if cursor is not None:
                self._mpl_cursors.append(cursor)

        self.ax.set_xlabel("Срок до погашения, лет")
        self.ax.set_ylabel("Доходность, %")
        self.ax.set_title(title)
        self.ax.grid(True, alpha=0.4)
        self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

        hover_text = " Наведение работает через mplcursors." if mplcursors is not None else " Для hover установи mplcursors."
        self.info.configure(text=f"Построено в окне GUI. Загружено кривых: {len(curves)} — {list(curves.keys())}.{hover_text}")

    def _plot_plotly(self, curves, title):
        fig = go.Figure()
        for curve_date, df in curves.items():
            df = df.sort_values("period").copy()
            custom = df[["tradedate", "tradetime", "period", "value"]].to_numpy()
            fig.add_trace(go.Scatter(
                x=df["period"],
                y=df["value"],
                mode="lines+markers",
                name=str(curve_date),
                customdata=custom,
                hovertemplate=(
                    "Дата: %{customdata[0]}<br>"
                    "Время: %{customdata[1]}<br>"
                    "Срок: %{customdata[2]:.4f} лет<br>"
                    "Доходность: %{customdata[3]:.4f}%"
                    "<extra>%{fullData.name}</extra>"
                ),
            ))

        fig.update_layout(
            title=title,
            xaxis_title="Срок до погашения, лет",
            yaxis_title="Доходность, %",
            hovermode="closest",
            template="plotly_white",
        )
        path = open_plotly_figure(fig, "zcyc_curve_rub", self.plotly_output.get())
        self.info.configure(text=f"Открыт Plotly {self.plotly_output.get()}: {path.name}. Загружено кривых: {len(curves)} — {list(curves.keys())}")


class ExternalCurveTab(ttk.Frame):

    SOURCE_LABELS = {
        "USD": "U.S. Treasury Daily Treasury Par Yield Curve Rates",
        "CNY": "ChinaBond Government Bond Yield Curve",
    }

    def __init__(self, parent, currency: str = "USD"):
        super().__init__(parent, padding=8)
        self.currency = str(currency).upper()
        if self.currency not in ("USD", "CNY"):
            raise ValueError("ExternalCurveTab поддерживает только USD и CNY")
        self.curve_df = pd.DataFrame()
        self._mpl_cursors = []

        controls = ttk.LabelFrame(self, text=f"ZCYC Curve {self.currency} — загрузка с сайта")
        controls.pack(fill="x", padx=4, pady=4)
        for col in range(7):
            controls.columnconfigure(col, weight=1)

        ttk.Label(controls, text="Curve Date:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.curve_date = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        ttk.Entry(controls, textvariable=self.curve_date, width=14).grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(controls, text="Источник:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Label(controls, text=self.SOURCE_LABELS[self.currency], foreground="#555").grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(controls, text="Библиотека:").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.chart_lib = tk.StringVar(value="Matplotlib (встроенный)")
        ttk.Combobox(
            controls,
            textvariable=self.chart_lib,
            values=["Matplotlib (встроенный)", "Plotly"],
            state="readonly",
            width=20,
        ).grid(row=0, column=5, sticky="we", padx=4, pady=2)

        ttk.Label(controls, text="Plotly output:").grid(row=1, column=4, sticky="w", padx=4, pady=2)
        self.plotly_output = tk.StringVar(value="HTML")
        ttk.Combobox(
            controls,
            textvariable=self.plotly_output,
            values=["HTML", "PNG"],
            state="readonly",
            width=8,
        ).grid(row=1, column=5, sticky="we", padx=4, pady=2)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=4, pady=2)
        self.load_plot_button = tk.Button(
            btns,
            text="Загрузить и построить кривую",
            command=self._load_and_plot,
            relief="raised",
            padx=10,
            **ACTION_BUTTON_GREEN,
        )
        self.load_plot_button.pack(side="left", padx=4)
        ttk.Button(btns, text="Очистить график", command=self._clear_plot).pack(side="left", padx=4)
        if self.currency == "USD":
            hint = "USD: загружается годовая таблица Treasury по году Curve Date; берётся последняя дата <= Curve Date."
        else:
            hint = "CNY: загружается ChinaBond annual standard terms download; берётся последняя дата <= Curve Date."
        ttk.Label(btns, text=hint, foreground="#777").pack(side="left", padx=12)

        discount_controls = ttk.LabelFrame(self, text=f"Discount factor по ZCYC Curve {self.currency}")
        discount_controls.pack(fill="x", padx=4, pady=4)
        for col in range(7):
            discount_controls.columnconfigure(col, weight=1)
        ttk.Label(discount_controls, text="Target Date:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.df_target_date = tk.StringVar(value="2026-12-31")
        ttk.Entry(discount_controls, textvariable=self.df_target_date, width=14).grid(row=0, column=1, sticky="we", padx=4, pady=2)
        ttk.Label(discount_controls, text="Amount:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.df_amount = tk.StringVar(value="1000000")
        ttk.Entry(discount_controls, textvariable=self.df_amount, width=14).grid(row=0, column=3, sticky="we", padx=4, pady=2)
        ttk.Label(discount_controls, text="Direction:").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.df_direction = tk.StringVar(value="PV: future → today")
        ttk.Combobox(
            discount_controls,
            textvariable=self.df_direction,
            values=["PV: future → today", "FV: today → future"],
            state="readonly",
            width=20,
        ).grid(row=0, column=5, sticky="we", padx=4, pady=2)
        ttk.Button(discount_controls, text="Рассчитать DF", command=self._calculate_discount_factor).grid(row=0, column=6, sticky="we", padx=8, pady=2)
        ttk.Label(
            discount_controls,
            text="DF = exp(-rT), r берётся интерполяцией по загруженной кривой на Curve Date",
            foreground="#777",
        ).grid(row=1, column=0, columnspan=7, sticky="w", padx=4, pady=2)
        self.discount_result = ttk.Label(self, text="", foreground="#333")
        self.discount_result.pack(anchor="w", padx=8, pady=2)

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)
        table_box = ttk.LabelFrame(body, text="Точки кривой")
        plot_box = ttk.LabelFrame(body, text=f"График ZCYC Curve {self.currency}")
        body.add(table_box, weight=1)
        body.add(plot_box, weight=2)

        self.result = make_result_box(table_box)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_box)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_box)
        self.toolbar.update()

        self.info = ttk.Label(
            self,
            text=f"ZCYC Curve {self.currency}: нажми загрузить, чтобы получить последнюю доступную точку на дату <= Curve Date.",
            foreground="#555",
        )
        self.info.pack(anchor="w", padx=6, pady=2)

        for var in (self.curve_date, self.chart_lib, self.plotly_output):
            try:
                var.trace_add("write", self._mark_load_plot_pending)
            except Exception:
                pass

    def _mark_load_plot_pending(self, *_):
        if hasattr(self, "load_plot_button"):
            set_action_button_state(self.load_plot_button, pending=True)

    def _mark_load_plot_done(self):
        if hasattr(self, "load_plot_button"):
            set_action_button_state(self.load_plot_button, pending=False)

    def _load_curve(self):
        curve_date = self.curve_date.get().strip()
        parse_date(curve_date, "Curve Date")
        curve = ratescurves.get_external_curve(self.currency, curve_date)
        self.curve_df = curve
        return curve

    def _load_and_plot(self):
        try:
            curve = self._load_curve()
            self._show_curve_table(curve)
            if self.chart_lib.get().startswith("Matplotlib"):
                self._plot_matplotlib(curve)
            else:
                self._plot_plotly(curve)
            self._mark_load_plot_done()
        except Exception as e:
            show_error(f"Ошибка загрузки ZCYC Curve {self.currency}", e)

    def _show_curve_table(self, curve: pd.DataFrame):
        if curve is None or curve.empty:
            write_result(self.result, "Нет данных")
            return
        shown = curve.copy()
        preferred = ["Currency", "Label", "period", "value", "Observation Date", "Source", "Status"]
        shown = shown[[c for c in preferred if c in shown.columns]]
        for col in ("period", "value"):
            if col in shown.columns:
                shown[col] = pd.to_numeric(shown[col], errors="coerce").map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
        write_result(self.result, shown.to_string(index=False))

    def _ok_curve_points(self, curve: pd.DataFrame) -> pd.DataFrame:
        df = curve.copy()
        df["period"] = pd.to_numeric(df["period"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        if "Status" in df.columns:
            ok = df[df["Status"].astype(str) == "OK"].copy()
        else:
            ok = df.copy()
        ok = ok.dropna(subset=["period", "value"]).sort_values("period")
        if ok.empty:
            raise ValueError("Нет OK-точек для графика")
        return ok

    def _plot_matplotlib(self, curve: pd.DataFrame):
        ok = self._ok_curve_points(curve)
        self.ax.clear()
        line, = self.ax.plot(ok["period"], ok["value"], marker="o", label=self.currency)
        labels = []
        for _, row in ok.iterrows():
            labels.append(
                f"Currency: {row.get('Currency', self.currency)}\n"
                f"Label: {row.get('Label', '')}\n"
                f"T: {float(row.get('period', np.nan)):.6f}\n"
                f"Yield: {float(row.get('value', np.nan)):.6f}%\n"
                f"Obs date: {row.get('Observation Date', '')}\n"
                f"Source: {row.get('Source', '')}"
            )
        cursor = add_mpl_hover(line, labels)
        self._mpl_cursors = [cursor] if cursor is not None else []
        obs_dates = sorted(ok.get("Observation Date", pd.Series(dtype=str)).astype(str).unique().tolist())
        obs_text = obs_dates[-1] if obs_dates else self.curve_date.get()
        self.ax.set_title(f"ZCYC Curve {self.currency} на {obs_text}")
        self.ax.set_xlabel("Maturity, years")
        self.ax.set_ylabel("Yield, %")
        self.ax.grid(True, alpha=0.4)
        self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()
        self.info.configure(text=f"Загружено точек: {len(ok)}. Currency={self.currency}. Observation date={obs_text}.")

    def _plot_plotly(self, curve: pd.DataFrame):
        ok = self._ok_curve_points(curve)
        fig = go.Figure()
        custom_cols = [c for c in ["Label", "Observation Date", "Source", "Status"] if c in ok.columns]
        custom = ok[custom_cols].to_numpy() if custom_cols else None
        hover = (
            "Label: %{customdata[0]}<br>"
            "Observation date: %{customdata[1]}<br>"
            "Source: %{customdata[2]}<br>"
            "Maturity: %{x:.6f} years<br>"
            "Yield: %{y:.6f}%"
            "<extra>%{fullData.name}</extra>"
        ) if len(custom_cols) >= 3 else None
        fig.add_trace(go.Scatter(
            x=ok["period"],
            y=ok["value"],
            mode="lines+markers",
            name=self.currency,
            customdata=custom,
            hovertemplate=hover,
        ))
        obs_dates = sorted(ok.get("Observation Date", pd.Series(dtype=str)).astype(str).unique().tolist())
        obs_text = obs_dates[-1] if obs_dates else self.curve_date.get()
        fig.update_layout(
            title=f"ZCYC Curve {self.currency} на {obs_text}",
            xaxis_title="Maturity, years",
            yaxis_title="Yield, %",
            hovermode="closest",
            template="plotly_white",
        )
        path = open_plotly_figure(fig, f"zcyc_curve_{self.currency.lower()}", self.plotly_output.get())
        self.info.configure(text=f"Открыт Plotly {self.plotly_output.get()}: {path.name}. Currency={self.currency}. Observation date={obs_text}.")

    def _calculate_discount_factor(self):
        try:
            if self.curve_df is None or self.curve_df.empty:
                self._load_curve()
                self._show_curve_table(self.curve_df)
            curve_date = self.curve_date.get().strip()
            target_date = self.df_target_date.get().strip()
            parse_date(curve_date, "Curve Date")
            parse_date(target_date, "Target Date")
            amount = parse_float(self.df_amount.get(), "Amount")
            T = ratescurves.years_between(curve_date, target_date)
            if T <= 0:
                raise ValueError("Target Date должна быть позже Curve Date")
            factors = ratescurves.discount_factors_from_curve(self.curve_df, T, compounding="continuous")
            df = factors["Discount Factor"]
            gf = factors["Growth Factor"]
            rate = factors["Rate Percent"]
            if self.df_direction.get().startswith("PV"):
                multiplier = df
                result = amount * df
                direction_text = "умножить будущую сумму на DF, чтобы получить текущую справедливую стоимость"
            else:
                multiplier = gf
                result = amount * gf
                direction_text = "умножить текущую сумму на Growth Factor, чтобы получить будущую справедливую стоимость"
            self.discount_result.configure(
                text=(
                    f"T={T:.6f} лет | interpolated rate={rate:.6f}% | "
                    f"DF={df:.10f} | Growth Factor={gf:.10f} | "
                    f"нужный множитель={multiplier:.10f} | Result={result:,.6f}. "
                    f"Смысл: {direction_text}."
                ).replace(",", " ")
            )
        except Exception as e:
            show_error(f"Ошибка расчёта discount factor {self.currency}", e)

    def _clear_plot(self):
        self.ax.clear()
        self.ax.set_title(f"ZCYC Curve {self.currency}")
        self.ax.grid(True, alpha=0.4)
        self.canvas.draw()
        self.info.configure(text="График очищен")


class VolSurfaceTab(ttk.Frame):

    INPUT_COLUMNS = ("Ticker", "Strike", "Expiry Date", "Market Price", "Option Type")
    OUTPUT_COLUMNS = (
        "Ticker", "Strike", "Expiry Date", "T", "Market Price", "Option Type",
        "Option Style", "Engine",
        "Implied Vol", "Model Price", "Error",
        "Delta", "Gamma", "Vega", "Theta", "Rho", "Status"
    )
    PLOTTABLE_METRICS = (
        "Implied Vol", "Market Price", "Model Price",
        "Delta", "Gamma", "Vega", "Theta", "Rho"
    )

    def __init__(self, parent):
        super().__init__(parent, padding=8)
        self.result_df = pd.DataFrame()
        self._mpl_cursors = []

        params = ttk.LabelFrame(self, text="Общие параметры Vol Surface")
        params.pack(fill="x", padx=4, pady=4)
        for col in range(6):
            params.columnconfigure(col, weight=1)

        self.asset_cb = LabeledCombo(
            params, 0, "Asset Type:", ["Equity", "Index", "FX", "Commodity"],
            default="Equity", width=14, on_change=self._update_fields
        )
        self.option_style_cb = LabeledCombo(
            params, 1, "Option Style:", ["European", "American"],
            default="European", width=14, on_change=self._update_fields
        )

        self._vol_surface_american_engine = "Trinomial"
        self.default_cp_cb = LabeledCombo(
            params, 2, "Default Option Type:", ["Call", "Put"],
            default="Call", width=14
        )
        self.S = LabeledEntry(params, 3, "S / Spot:", default="62.16")
        self.Rd = LabeledEntry(params, 4, "Rd:", default="0.0425")
        self.Rf = LabeledEntry(params, 5, "Rf:", default="0.025")
        self.q = LabeledEntry(params, 6, "q:", default="0.0")
        self.val_date = LabeledEntry(
            params, 7, "Valuation Date:",
            default=datetime.today().strftime("%Y-%m-%d"), hint="YYYY-MM-DD"
        )

        solver = ttk.LabelFrame(self, text="Параметры solver")
        solver.pack(fill="x", padx=4, pady=4)
        solver.columnconfigure(1, weight=1)
        self.low_vol = LabeledEntry(solver, 0, "low_vol:", default="0.0001")
        self.high_vol = LabeledEntry(solver, 1, "high_vol:", default="5.0")
        self.tol = LabeledEntry(solver, 2, "tol:", default="1e-6")
        self.max_iter = LabeledEntry(solver, 3, "max_iter:", default="100")
        self.n_steps = LabeledEntry(solver, 4, "N steps American:", default="200")


        self._vol_surface_poly_degree = 3
        self._vol_surface_div_dates = ""
        self._vol_surface_div_amounts = ""
        self.american_param_widgets = [
            self.n_steps.entry,
        ]
        ttk.Label(
            solver,
            text="American options считаются через универсальное Trinomial Tree для Equity/Index/FX/Commodity. Если Model Price отличается от Market Price более чем на 15%, строка получает WARNING.",
            foreground="#777",
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=4, pady=2)

        row_frame = ttk.LabelFrame(self, text="Ввод рыночных опционных котировок")
        row_frame.pack(fill="x", padx=4, pady=4)
        for col in range(10):
            row_frame.columnconfigure(col, weight=1)

        ttk.Label(row_frame, text="Ticker").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.row_ticker = tk.StringVar(value="D-C-20260901-60")
        ttk.Entry(row_frame, textvariable=self.row_ticker, width=16).grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Strike").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.row_strike = tk.StringVar(value="60")
        ttk.Entry(row_frame, textvariable=self.row_strike, width=12).grid(row=0, column=3, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Expiry Date").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.row_expiry = tk.StringVar(value="2026-09-01")
        ttk.Entry(row_frame, textvariable=self.row_expiry, width=14).grid(row=0, column=5, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Market Price").grid(row=0, column=6, sticky="w", padx=4, pady=2)
        self.row_price = tk.StringVar(value="5.10")
        ttk.Entry(row_frame, textvariable=self.row_price, width=12).grid(row=0, column=7, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Option Type").grid(row=0, column=8, sticky="w", padx=4, pady=2)
        self.row_cp = tk.StringVar(value="Call")
        self.row_cp_combo = ttk.Combobox(row_frame, textvariable=self.row_cp, values=["Call", "Put"], state="readonly", width=8)
        self.row_cp_combo.grid(row=0, column=9, sticky="we", padx=4, pady=2)

        btns = ttk.Frame(row_frame)
        btns.grid(row=1, column=0, columnspan=10, sticky="w", padx=4, pady=4)
        ttk.Button(btns, text="Добавить строку", command=self._add_input_row).pack(side="left", padx=2)
        ttk.Button(btns, text="Удалить выбранную", command=self._delete_selected_input_rows).pack(side="left", padx=2)
        ttk.Button(btns, text="Очистить таблицу", command=self._clear_input_rows).pack(side="left", padx=2)
        ttk.Button(btns, text="Загрузить из CSV/Excel", command=self._load_market_file).pack(side="left", padx=2)
        self.calc_button = tk.Button(
            btns,
            text="Рассчитать implied vols",
            command=self._calculate,
            bg="#28a745",
            fg="white",
            activebackground="#218838",
            activeforeground="white",
            relief="raised",
            padx=10,
        )
        self.calc_button.pack(side="left", padx=10)
        ttk.Button(btns, text="Сохранить результат", command=self._save_result).pack(side="left", padx=2)

        tables = ttk.PanedWindow(self, orient="horizontal")
        tables.pack(fill="x", expand=False, padx=4, pady=4)
        input_box = ttk.LabelFrame(tables, text="Входная таблица")
        output_box = ttk.LabelFrame(tables, text="Результат расчёта")
        tables.add(input_box, weight=1)
        tables.add(output_box, weight=1)

        self.input_tree = self._make_tree(input_box, self.INPUT_COLUMNS, height=6)
        self.output_tree = self._make_tree(output_box, self.OUTPUT_COLUMNS, height=6)
        self.output_tree.tag_configure("status_ok", background="#DFF2BF")
        self.output_tree.tag_configure("status_warning", background="#FFF2CC")
        self.output_tree.tag_configure("status_error", background="#FFD2D2")

        self._insert_demo_rows()

        plot_controls = ttk.LabelFrame(self, text="Графики")
        plot_controls.pack(fill="x", padx=4, pady=4)

        ttk.Label(plot_controls, text="Библиотека:").pack(side="left", padx=4)
        self.chart_lib = tk.StringVar(value="Plotly")
        ttk.Combobox(
            plot_controls,
            textvariable=self.chart_lib,
            values=["Plotly", "Matplotlib (встроенный)"],
            state="readonly",
            width=22,
        ).pack(side="left", padx=4)

        ttk.Label(plot_controls, text="Plotly output:").pack(side="left", padx=(10, 4))
        self.plotly_output = tk.StringVar(value="HTML")
        ttk.Combobox(
            plot_controls,
            textvariable=self.plotly_output,
            values=["HTML", "PNG"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=4)

        ttk.Label(plot_controls, text="Метрика:", font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=(12, 4))
        self.plot_metric = tk.StringVar(value="Implied Vol")
        ttk.Combobox(
            plot_controls,
            textvariable=self.plot_metric,
            values=list(self.PLOTTABLE_METRICS),
            state="readonly",
            width=15,
        ).pack(side="left", padx=4)

        ttk.Label(plot_controls, text="Expiry для 2D:").pack(side="left", padx=(12, 4))
        self.expiry_for_2d = tk.StringVar(value="")
        self.expiry_combo = ttk.Combobox(plot_controls, textvariable=self.expiry_for_2d, values=[], state="readonly", width=16)
        self.expiry_combo.pack(side="left", padx=4)
        ttk.Button(plot_controls, text="Построить 2D", command=self._plot_2d).pack(side="left", padx=4)

        ttk.Label(plot_controls, text="3D mode:").pack(side="left", padx=(12, 4))
        self.surface_mode = tk.StringVar(value="Interpolated Surface")
        ttk.Combobox(plot_controls, textvariable=self.surface_mode,
                     values=["3D Scatter", "Interpolated Surface"], state="readonly", width=20).pack(side="left", padx=4)
        self.plot_3d_button = tk.Button(
            plot_controls,
            text="Построить 3D",
            command=self._plot_3d,
            relief="raised",
            padx=10,
            **ACTION_BUTTON_GREEN,
        )
        self.plot_3d_button.pack(side="left", padx=4)

        for var in (self.plot_metric, self.surface_mode, self.chart_lib, self.plotly_output):
            try:
                var.trace_add("write", self._mark_3d_plot_pending)
            except Exception:
                pass

        self.plot_frame = ttk.LabelFrame(self, text="Matplotlib preview для Vol Surface")
        self.plot_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.fig = Figure(figsize=(9, 5.4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()

        self.info = ttk.Label(
            self,
            text="Демо-набор сгенерирован расчётным модулем. European — parity-consistent, American — через Trinomial Tree.",
            foreground="#555",
        )
        self.info.pack(anchor="w", padx=6, pady=2)
        self._bind_recalc_triggers()
        self._update_fields()

    def _make_tree(self, parent, columns, height=8):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col in columns:
            tree.heading(col, text=col)
            if col == "Ticker":
                width = 135
            elif col == "Status":
                width = 300
            elif col in ("Option Style", "Engine"):
                width = 115
            elif col in ("Delta", "Gamma", "Vega", "Theta", "Rho"):
                width = 105
            else:
                width = 110
            tree.column(col, width=width, anchor="center", stretch=True)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def _update_fields(self):
        asset = self.asset_cb.get()
        style = self.option_style_cb.get() if hasattr(self, "option_style_cb") else "European"
        self.Rf.entry.configure(state="normal" if asset in ("FX", "Commodity") else "disabled")
        self.q.entry.configure(state="normal" if asset in ("Equity", "Index") else "disabled")

        american_state = "normal" if style == "American" else "disabled"
        if hasattr(self, "american_param_widgets"):
            for widget in self.american_param_widgets:
                try:
                    widget.configure(state=american_state)
                except tk.TclError:
                    pass

        self._mark_calculation_pending()

    def _mark_calculation_pending(self, *_):
        if hasattr(self, "calc_button"):
            self.calc_button.configure(
                bg="#28a745", fg="white", activebackground="#218838", activeforeground="white",
                text="Рассчитать implied vols",
            )

    def _mark_calculation_done(self):
        if hasattr(self, "calc_button"):
            self.calc_button.configure(
                bg="#E0E0E0", fg="black", activebackground="#D5D5D5", activeforeground="black",
                text="Implied vols рассчитаны",
            )
        self._mark_3d_plot_pending()

    def _mark_3d_plot_pending(self, *_):
        if hasattr(self, "plot_3d_button"):
            set_action_button_state(self.plot_3d_button, pending=True)

    def _mark_3d_plot_done(self):
        if hasattr(self, "plot_3d_button"):
            set_action_button_state(self.plot_3d_button, pending=False)

    def _bind_recalc_triggers(self):
        entries = [
            self.S.entry, self.Rd.entry, self.Rf.entry, self.q.entry, self.val_date.entry,
            self.low_vol.entry, self.high_vol.entry, self.tol.entry, self.max_iter.entry,
            self.n_steps.entry,
        ]
        for entry in entries:
            entry.bind("<KeyRelease>", self._mark_calculation_pending, add="+")
        for combo in (self.asset_cb.combo, self.option_style_cb.combo, self.default_cp_cb.combo, self.row_cp_combo):
            combo.bind("<<ComboboxSelected>>", self._mark_calculation_pending, add="+")

    def _insert_demo_rows(self, clear_existing: bool = False):

        if clear_existing:
            self._clear_tree(self.input_tree)

        try:
            S = parse_float(self.S.get(), "S")
            Rd = parse_float(self.Rd.get(), "Rd")
            Rf = parse_float(self.Rf.get(), "Rf") if self.asset_cb.get() in ("FX", "Commodity") else 0.0
            q = parse_float(self.q.get(), "q") if self.asset_cb.get() in ("Equity", "Index") else 0.0
            valuation_date = parse_date(self.val_date.get(), "Valuation Date")

            demo_df = volsurf.generate_demo_market_data(
                pricing_module=pricing,
                asset_type=self.asset_cb.get(),
                option_style=self.option_style_cb.get(),
                american_engine=self._vol_surface_american_engine,
                S=S,
                Rd=Rd,
                Rf=Rf,
                q=q,
                valuation_date=valuation_date,
                n_steps=parse_int(self.n_steps.get(), "N steps"),
                poly_degree=self._vol_surface_poly_degree,
                div_dates=self._vol_surface_div_dates,
                div_amounts=self._vol_surface_div_amounts,
            )
            demo = [
                (
                    str(row["Ticker"]),
                    f"{float(row['Strike']):g}",
                    str(row["Expiry Date"]),
                    f"{float(row['Market Price']):.6f}",
                    str(row["Option Type"]),
                )
                for _, row in demo_df.iterrows()
            ]
        except Exception:

            demo = [
                ("D-C-20260901-60", "60", "2026-09-01", "5.1000", "Call"),
                ("D-P-20260901-60", "60", "2026-09-01", "2.7000", "Put"),
            ]

        for values in demo:
            self.input_tree.insert("", "end", values=values)
        self._mark_calculation_pending()

        if clear_existing:
            self.result_df = pd.DataFrame()
            self._clear_tree(self.output_tree)
            self.expiry_combo.configure(values=[])
            self.expiry_for_2d.set("")
            self.info.configure(text=f"Загружен demo-набор Call/Put для {self.option_style_cb.get()}: {len(demo)} строк")

    def _add_input_row(self):
        try:
            ticker = self.row_ticker.get().strip()
            strike = parse_float(self.row_strike.get(), "Strike")
            expiry = parse_date(self.row_expiry.get(), "Expiry Date").strftime("%Y-%m-%d")
            price = parse_float(self.row_price.get(), "Market Price")
            cp = self.row_cp.get()
            self.input_tree.insert("", "end", values=(ticker, f"{strike:g}", expiry, f"{price:g}", cp))
            self._mark_calculation_pending()
        except Exception as e:
            show_error("Ошибка добавления строки", e)

    def _delete_selected_input_rows(self):
        for item in self.input_tree.selection():
            self.input_tree.delete(item)
        self._mark_calculation_pending()

    def _clear_input_rows(self):
        for item in self.input_tree.get_children():
            self.input_tree.delete(item)
        self.result_df = pd.DataFrame()
        self._clear_tree(self.output_tree)
        self.expiry_combo.configure(values=[])
        self.expiry_for_2d.set("")
        self._mark_calculation_pending()
        self.info.configure(text="Входная таблица очищена")

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _tree_to_dataframe(self):
        rows = []
        for item in self.input_tree.get_children():
            values = self.input_tree.item(item, "values")
            if not values:
                continue
            rows.append(dict(zip(self.INPUT_COLUMNS, values)))
        if not rows:
            raise ValueError("Входная таблица пустая")
        return pd.DataFrame(rows)

    def _load_market_file(self):
        try:
            path = filedialog.askopenfilename(
                title="Выбери CSV/Excel с котировками",
                filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
            )
            if not path:
                return
            df = volsurf.load_market_data(path)
            df = volsurf._standardize_market_data_columns(df)
            self._clear_tree(self.input_tree)
            default_cp = self.default_cp_cb.get()
            for _, row in df.iterrows():
                ticker = row["Ticker"] if "Ticker" in df.columns and pd.notna(row.get("Ticker")) else ""
                cp = row["Option Type"] if "Option Type" in df.columns and pd.notna(row.get("Option Type")) else default_cp
                self.input_tree.insert(
                    "", "end",
                    values=(ticker, row["Strike"], pd.to_datetime(row["Expiry Date"]).strftime("%Y-%m-%d"), row["Market Price"], cp)
                )
            self.result_df = pd.DataFrame()
            self._clear_tree(self.output_tree)
            self._update_expiry_combo(pd.DataFrame(columns=self.OUTPUT_COLUMNS))
            self._mark_calculation_pending()
            self.info.configure(text=f"Загружено строк: {len(df)} из {path}")
        except Exception as e:
            show_error("Ошибка загрузки файла", e)

    def _calculate(self):
        try:
            market_df = self._tree_to_dataframe()
            valuation_date = parse_date(self.val_date.get(), "Valuation Date")
            S = parse_float(self.S.get(), "S")
            Rd = parse_float(self.Rd.get(), "Rd")
            Rf = parse_float(self.Rf.get(), "Rf") if self.asset_cb.get() in ("FX", "Commodity") else 0.0
            q = parse_float(self.q.get(), "q") if self.asset_cb.get() in ("Equity", "Index") else 0.0

            result = volsurf.calculate_vol_surface(
                market_data=market_df,
                S=S,
                Rd=Rd,
                Rf=Rf,
                q=q,
                asset_type=self.asset_cb.get(),
                option_style=self.option_style_cb.get(),
                american_engine=self._vol_surface_american_engine,
                valuation_date=valuation_date,
                default_option_type=self.default_cp_cb.get(),
                pricing_module=pricing,
                n_steps=parse_int(self.n_steps.get(), "N steps"),
                poly_degree=self._vol_surface_poly_degree,
                div_dates=self._vol_surface_div_dates,
                div_amounts=self._vol_surface_div_amounts,
                low_vol=parse_float(self.low_vol.get(), "low_vol"),
                high_vol=parse_float(self.high_vol.get(), "high_vol"),
                tol=parse_float(self.tol.get(), "tol"),
                max_iter=parse_int(self.max_iter.get(), "max_iter"),
                price_diff_warning_pct=15.0,
            )

            self.result_df = result
            self._fill_output_tree(result)
            self._update_expiry_combo(result)

            status_text = result["Status"].astype(str)
            ok_count = int((status_text == "OK").sum())
            warn_count = int(status_text.str.startswith("WARNING").sum())
            err_count = int(status_text.str.startswith("ERROR").sum())
            self._mark_calculation_done()
            self.info.configure(
                text=f"Расчёт завершён: OK={ok_count}, warnings={warn_count}, errors={err_count}. "
                     f"Style={self.option_style_cb.get()}, Engine={self._vol_surface_american_engine if self.option_style_cb.get() == 'American' else 'Analytical'}. "
                     f"Добавлены Delta/Gamma/Vega/Theta/Rho."
            )
        except Exception as e:
            show_error("Ошибка расчёта Vol Surface", e)

    def _fill_output_tree(self, df: pd.DataFrame):
        self._clear_tree(self.output_tree)
        for _, row in df.iterrows():
            values = []
            for col in self.OUTPUT_COLUMNS:
                value = row.get(col, "")
                if isinstance(value, float):
                    if pd.isna(value):
                        value = ""
                    elif col == "Implied Vol":
                        value = f"{value:.6f}"
                    elif col in ("T", "Model Price", "Market Price", "Error", "Delta", "Gamma", "Vega", "Theta", "Rho"):
                        value = f"{value:.6f}"
                    else:
                        value = f"{value:g}"
                values.append(value)

            status = str(row.get("Status", ""))
            if status.startswith("ERROR"):
                tag = "status_error"
            elif status.startswith("WARNING"):
                tag = "status_warning"
            else:
                tag = "status_ok"
            self.output_tree.insert("", "end", values=values, tags=(tag,))

    def _is_plottable_status(self, status: str) -> bool:
        status = str(status)
        return status == "OK" or status.startswith("WARNING")

    def _update_expiry_combo(self, df: pd.DataFrame):
        if df is None or df.empty or "Status" not in df.columns:
            expiries = []
        else:
            ok = df[df["Status"].astype(str).map(self._is_plottable_status)].copy()
            expiries = sorted(ok["Expiry Date"].dropna().astype(str).unique().tolist())
        self.expiry_combo.configure(values=expiries)
        self.expiry_for_2d.set(expiries[0] if expiries else "")

    def _get_ok_result(self):
        if self.result_df is None or self.result_df.empty:
            raise ValueError("Сначала рассчитай implied vols")
        ok = self.result_df[self.result_df["Status"].astype(str).map(self._is_plottable_status)].copy()
        if ok.empty:
            raise ValueError("Нет рассчитанных OK/WARNING строк для графика")
        return ok

    def _metric_info(self):
        metric = self.plot_metric.get() or "Implied Vol"
        if metric not in self.PLOTTABLE_METRICS:
            metric = "Implied Vol"
        if metric == "Implied Vol":
            return metric, "Implied volatility, %", lambda s: pd.to_numeric(s, errors="coerce") * 100.0
        return metric, metric, lambda s: pd.to_numeric(s, errors="coerce")

    def _format_metric_value(self, metric, value):
        try:
            value = float(value)
        except Exception:
            return ""
        if not np.isfinite(value):
            return ""
        if metric == "Implied Vol":
            return f"{value:.6f} ({value * 100.0:.4f}%)"
        return f"{value:.6f}"

    def _hover_custom_cols(self):
        return [
            "Ticker", "Expiry Date", "T", "Market Price", "Model Price", "Error",
            "Option Type", "Option Style", "Engine", "Implied Vol",
            "Delta", "Gamma", "Vega", "Theta", "Rho"
        ]

    def _plot_2d(self):
        try:
            if self.chart_lib.get().startswith("Matplotlib"):
                self._plot_2d_matplotlib()
            else:
                self._plot_2d_plotly()
        except Exception as e:
            show_error("Ошибка построения 2D графика", e)

    def _plot_3d(self):
        try:
            if self.chart_lib.get().startswith("Matplotlib"):
                self._plot_3d_matplotlib()
            else:
                self._plot_3d_plotly()
            self._mark_3d_plot_done()
        except Exception as e:
            show_error("Ошибка построения 3D графика", e)

    def _get_2d_subset(self):
        df = self._get_ok_result()
        expiry = self.expiry_for_2d.get()
        if not expiry:
            expiry = sorted(df["Expiry Date"].astype(str).unique())[0]
            self.expiry_for_2d.set(expiry)
        subset = df[df["Expiry Date"].astype(str) == str(expiry)].copy()
        if subset.empty:
            raise ValueError(f"Нет точек для expiry={expiry}")
        return subset.sort_values("Strike"), expiry

    def _plot_2d_plotly(self):
        subset, expiry = self._get_2d_subset()
        metric, axis_label, transform = self._metric_info()
        fig = go.Figure()

        for option_type, grp in subset.groupby("Option Type", sort=True):
            grp = grp.sort_values("Strike")
            y = transform(grp[metric])
            custom = grp[self._hover_custom_cols()].to_numpy()
            fig.add_trace(go.Scatter(
                x=grp["Strike"].astype(float),
                y=y,
                mode="lines+markers",
                name=f"{option_type} / {metric} / {expiry}",
                customdata=custom,
                hovertemplate=(
                    "Ticker: %{customdata[0]}<br>"
                    "Strike: %{x:.6g}<br>"
                    "Expiry: %{customdata[1]}<br>"
                    "T: %{customdata[2]:.6f}<br>"
                    "Option: %{customdata[6]}<br>"
                    "Style: %{customdata[7]}<br>"
                    "Engine: %{customdata[8]}<br>"
                    "IV: %{customdata[9]:.6f}<br>"
                    "Market Price: %{customdata[3]:.6f}<br>"
                    "Model Price: %{customdata[4]:.6f}<br>"
                    "Error: %{customdata[5]:.6e}<br>"
                    "Delta: %{customdata[10]:.6f}<br>"
                    "Gamma: %{customdata[11]:.6f}<br>"
                    "Vega: %{customdata[12]:.6f}<br>"
                    "Theta: %{customdata[13]:.6f}<br>"
                    "Rho: %{customdata[14]:.6f}<br>"
                    f"Selected metric ({metric}): " + "%{y:.6f}"
                    "<extra>%{fullData.name}</extra>"
                ),
            ))

        fig.update_layout(
            title=f"{metric} by Strike, expiry={expiry}",
            xaxis_title="Strike",
            yaxis_title=axis_label,
            hovermode="closest",
            template="plotly_white",
            legend_title="Option Type / Metric",
        )
        path = open_plotly_figure(fig, f"vol_surface_2d_{metric.lower().replace(' ', '_')}", self.plotly_output.get())
        self.info.configure(text=f"Открыт Plotly {self.plotly_output.get()} 2D-график: {path.name}. Метрика: {metric}.")

    def _plot_2d_matplotlib(self):
        subset, expiry = self._get_2d_subset()
        metric, axis_label, transform = self._metric_info()
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self._mpl_cursors = []

        for option_type, grp in subset.groupby("Option Type", sort=True):
            grp = grp.sort_values("Strike")
            x = grp["Strike"].astype(float).to_numpy()
            y = transform(grp[metric]).to_numpy()
            line, = self.ax.plot(x, y, marker="o", label=str(option_type))
            labels = [self._mpl_label(row, metric) for _, row in grp.iterrows()]
            cursor = add_mpl_hover(line, labels)
            if cursor is not None:
                self._mpl_cursors.append(cursor)

        self.ax.set_title(f"{metric} by Strike, expiry={expiry}")
        self.ax.set_xlabel("Strike")
        self.ax.set_ylabel(axis_label)
        self.ax.grid(True, alpha=0.4)
        self.ax.legend(title="Option Type")
        self.fig.tight_layout()
        self.canvas.draw()
        hover_text = " Наведение работает через mplcursors." if mplcursors is not None else " Для hover установи mplcursors."
        self.info.configure(text=f"2D-график построен через Matplotlib. Метрика: {metric}.{hover_text}")

    def _plot_3d_plotly(self):
        import numpy as np
        df = self._get_ok_result().copy()
        metric, axis_label, transform = self._metric_info()
        mode = self.surface_mode.get()
        fig = go.Figure()

        for option_type, grp in df.groupby("Option Type", sort=True):
            grp = grp.sort_values(["T", "Strike"])
            x = grp["Strike"].astype(float).to_numpy()
            y = grp["T"].astype(float).to_numpy()
            z = transform(grp[metric]).to_numpy()

            valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
            x, y, z = x[valid], y[valid], z[valid]
            grp_valid = grp.loc[valid].copy()
            if len(grp_valid) == 0:
                continue

            if mode == "Interpolated Surface" and len(grp_valid) >= 4 and len(set(x)) >= 2 and len(set(y)) >= 2:
                try:
                    from scipy.interpolate import griddata
                    xi = np.linspace(np.nanmin(x), np.nanmax(x), 45)
                    yi = np.linspace(np.nanmin(y), np.nanmax(y), 45)
                    X, Y = np.meshgrid(xi, yi)
                    Z = griddata((x, y), z, (X, Y), method="linear")
                    fig.add_trace(go.Surface(
                        x=xi, y=yi, z=Z,
                        name=f"{option_type} {metric} surface",
                        opacity=0.45,
                        showscale=(option_type == sorted(df["Option Type"].astype(str).unique())[0]),
                        colorbar=dict(title=axis_label),
                        hovertemplate=(
                            "Option: " + str(option_type) + "<br>"
                            "Strike: %{x:.6g}<br>"
                            "T: %{y:.6f}<br>"
                            f"Interpolated {metric}: " + "%{z:.6f}"
                            "<extra></extra>"
                        ),
                    ))
                except Exception as interp_error:
                    messagebox.showwarning("Интерполяция недоступна", f"Не удалось построить поверхность для {option_type}.\n\n{interp_error}")

            custom = grp_valid[self._hover_custom_cols()].to_numpy()
            fig.add_trace(go.Scatter3d(
                x=x, y=y, z=z,
                mode="markers",
                name=f"{option_type} {metric} points",
                customdata=custom,
                marker=dict(size=6),
                hovertemplate=(
                    "Ticker: %{customdata[0]}<br>"
                    "Strike: %{x:.6g}<br>"
                    "Expiry: %{customdata[1]}<br>"
                    "T: %{customdata[2]:.6f}<br>"
                    "Option: %{customdata[6]}<br>"
                    "Style: %{customdata[7]}<br>"
                    "Engine: %{customdata[8]}<br>"
                    "IV: %{customdata[9]:.6f}<br>"
                    "Market Price: %{customdata[3]:.6f}<br>"
                    "Model Price: %{customdata[4]:.6f}<br>"
                    "Error: %{customdata[5]:.6e}<br>"
                    "Delta: %{customdata[10]:.6f}<br>"
                    "Gamma: %{customdata[11]:.6f}<br>"
                    "Vega: %{customdata[12]:.6f}<br>"
                    "Theta: %{customdata[13]:.6f}<br>"
                    "Rho: %{customdata[14]:.6f}<br>"
                    f"Selected metric ({metric}): " + "%{z:.6f}"
                    "<extra>%{fullData.name}</extra>"
                ),
            ))

        fig.update_layout(
            title=f"{metric} Surface",
            template="plotly_white",
            scene=dict(xaxis_title="Strike", yaxis_title="Time to expiry, T", zaxis_title=axis_label),
            legend=dict(orientation="h"),
        )
        path = open_plotly_figure(fig, f"vol_surface_3d_{metric.lower().replace(' ', '_')}", self.plotly_output.get())
        self.info.configure(text=f"Открыт Plotly {self.plotly_output.get()} 3D-график: {path.name}. Метрика: {metric}.")

    def _plot_3d_matplotlib(self):
        import numpy as np
        from mpl_toolkits.mplot3d import Axes3D
        df = self._get_ok_result().copy()
        metric, axis_label, transform = self._metric_info()
        mode = self.surface_mode.get()
        self.fig.clear()
        self.ax = self.fig.add_subplot(111, projection="3d")
        self._mpl_cursors = []

        for option_type, grp in df.groupby("Option Type", sort=True):
            grp = grp.sort_values(["T", "Strike"])
            x = grp["Strike"].astype(float).to_numpy()
            y = grp["T"].astype(float).to_numpy()
            z = transform(grp[metric]).to_numpy()
            valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
            x, y, z = x[valid], y[valid], z[valid]
            grp_valid = grp.loc[valid].copy()
            if len(grp_valid) == 0:
                continue

            if mode == "Interpolated Surface" and len(grp_valid) >= 4 and len(set(x)) >= 2 and len(set(y)) >= 2:
                try:
                    from scipy.interpolate import griddata
                    xi = np.linspace(np.nanmin(x), np.nanmax(x), 40)
                    yi = np.linspace(np.nanmin(y), np.nanmax(y), 40)
                    X, Y = np.meshgrid(xi, yi)
                    Z = griddata((x, y), z, (X, Y), method="linear")
                    self.ax.plot_surface(X, Y, Z, alpha=0.35)
                except Exception as interp_error:
                    messagebox.showwarning("Интерполяция недоступна", f"Не удалось построить поверхность для {option_type}.\n\n{interp_error}")

            scatter = self.ax.scatter(x, y, z, s=35, label=str(option_type))
            labels = [self._mpl_label(row, metric) for _, row in grp_valid.iterrows()]
            cursor = add_mpl_hover(scatter, labels)
            if cursor is not None:
                self._mpl_cursors.append(cursor)

        self.ax.set_title(f"{metric} Surface")
        self.ax.set_xlabel("Strike")
        self.ax.set_ylabel("Time to expiry, T")
        self.ax.set_zlabel(axis_label)
        self.ax.legend(title="Option Type")
        self.fig.tight_layout()
        self.canvas.draw()
        hover_text = " Наведение работает через mplcursors." if mplcursors is not None else " Для hover установи mplcursors."
        self.info.configure(text=f"3D-график построен через Matplotlib. Метрика: {metric}.{hover_text}")

    def _mpl_label(self, row, metric):
        return (
            f"Ticker: {row.get('Ticker', '')}\n"
            f"Strike: {float(row['Strike']):.6g}\n"
            f"Expiry: {row['Expiry Date']}\n"
            f"T: {float(row['T']):.6f}\n"
            f"Option: {row['Option Type']}\n"
            f"Style: {row.get('Option Style', '')}\n"
            f"Engine: {row.get('Engine', '')}\n"
            f"IV: {self._format_metric_value('Implied Vol', row.get('Implied Vol', np.nan))}\n"
            f"Market: {float(row['Market Price']):.6f}\n"
            f"Model: {float(row['Model Price']):.6f}\n"
            f"Error: {float(row['Error']):.6e}\n"
            f"Delta: {float(row.get('Delta', np.nan)):.6f}\n"
            f"Gamma: {float(row.get('Gamma', np.nan)):.6f}\n"
            f"Vega: {float(row.get('Vega', np.nan)):.6f}\n"
            f"Theta: {float(row.get('Theta', np.nan)):.6f}\n"
            f"Rho: {float(row.get('Rho', np.nan)):.6f}\n"
            f"Selected ({metric}): {self._format_metric_value(metric, row.get(metric, np.nan))}"
        )

    def _save_result(self):
        try:
            if self.result_df is None or self.result_df.empty:
                raise ValueError("Сначала рассчитай результат")
            path = filedialog.asksaveasfilename(
                title="Сохранить результат Vol Surface",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not path:
                return
            volsurf.save_result(self.result_df, path)
            self.info.configure(text=f"Результат сохранён: {path}")
        except Exception as e:
            show_error("Ошибка сохранения результата", e)


class MarketChainTab(ttk.Frame):

    PREVIEW_COLUMNS = (
        "Ticker", "Expiry Date", "Strike", "Option Type",
        "Bid", "Ask", "Last", "Mid Price", "Market Price",
        "Underlying Price", "Sigma", "Volume", "Open Interest", "Status",
    )

    def __init__(self, parent, vol_surface_tab=None, strategy_tab=None):
        super().__init__(parent, padding=8)
        self.vol_surface_tab = vol_surface_tab
        self.strategy_tab = strategy_tab
        self.raw_df = pd.DataFrame()
        self.normalized_df = pd.DataFrame()
        self.mapping_vars = {}

        top = ttk.LabelFrame(self, text="Market Chain Import — загрузка Excel / CSV")
        top.pack(fill="x", padx=4, pady=4)

        ttk.Label(
            top,
            text="Вспомогательное окно для загрузки данных из вашего файла Excel, шаблон файла Excel в папке с программой.",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", padx=4, pady=(4, 2))

        ttk.Button(top, text="Загрузить Excel/CSV", command=self._load_file).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Сохранить шаблон Excel", command=self._save_template).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Применить разметку", command=self._apply_mapping).pack(side="left", padx=12, pady=4)
        ttk.Button(top, text="Экспорт нормализованного файла", command=self._export_normalized).pack(side="left", padx=4, pady=4)

        self.set_underlying_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Передавать Underlying Price в S", variable=self.set_underlying_var).pack(side="left", padx=12, pady=4)

        transfer = ttk.LabelFrame(self, text="Отправка в рабочие вкладки")
        transfer.pack(fill="x", padx=4, pady=4)
        for c in range(12):
            transfer.columnconfigure(c, weight=1)

        ttk.Label(transfer, text="Asset Type:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.asset_type = tk.StringVar(value="Equity")
        ttk.Combobox(transfer, textvariable=self.asset_type, values=["Equity", "Index", "FX", "Commodity"], state="readonly", width=12).grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(transfer, text="Style:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.option_style = tk.StringVar(value="European")
        ttk.Combobox(transfer, textvariable=self.option_style, values=["European", "American"], state="readonly", width=12).grid(row=0, column=3, sticky="we", padx=4, pady=2)

        ttk.Label(transfer, text="Strategy Side:").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.strategy_side = tk.StringVar(value="Buy")
        ttk.Combobox(transfer, textvariable=self.strategy_side, values=["Buy", "Sell"], state="readonly", width=8).grid(row=0, column=5, sticky="we", padx=4, pady=2)

        ttk.Label(transfer, text="Qty:").grid(row=0, column=6, sticky="w", padx=4, pady=2)
        self.strategy_qty = tk.StringVar(value="1")
        ttk.Entry(transfer, textvariable=self.strategy_qty, width=8).grid(row=0, column=7, sticky="we", padx=4, pady=2)

        ttk.Label(transfer, text="Sigma:").grid(row=0, column=8, sticky="w", padx=4, pady=2)
        self.sigma_mode = tk.StringVar(value="Sigma column / fallback fixed")
        ttk.Combobox(transfer, textvariable=self.sigma_mode,
                     values=["Sigma column / fallback fixed", "Fixed sigma"], state="readonly", width=24).grid(row=0, column=9, sticky="we", padx=4, pady=2)

        ttk.Label(transfer, text="Fixed sigma:").grid(row=0, column=10, sticky="w", padx=4, pady=2)
        self.fixed_sigma = tk.StringVar(value="0.20")
        ttk.Entry(transfer, textvariable=self.fixed_sigma, width=8).grid(row=0, column=11, sticky="we", padx=4, pady=2)

        self.strategy_import_mode = tk.StringVar(value="Replace")
        ttk.Label(transfer, text="Strategy mode:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Combobox(transfer, textvariable=self.strategy_import_mode, values=["Replace", "Append"], state="readonly", width=10).grid(row=1, column=1, sticky="we", padx=4, pady=2)

        tk.Button(transfer, text="Отправить в Vol Surface", command=lambda: self._send_to_vol_surface(calculate=False),
                  bg="#28a745", fg="white", activebackground="#218838", activeforeground="white").grid(row=1, column=2, columnspan=2, sticky="we", padx=6, pady=4)
        tk.Button(transfer, text="Vol Surface + расчёт", command=lambda: self._send_to_vol_surface(calculate=True),
                  bg="#20c997", fg="white", activebackground="#17a589", activeforeground="white").grid(row=1, column=4, columnspan=2, sticky="we", padx=6, pady=4)
        tk.Button(transfer, text="Отправить в Option Strategy", command=self._send_to_strategy,
                  bg="#007bff", fg="white", activebackground="#0069d9", activeforeground="white").grid(row=1, column=6, columnspan=3, sticky="we", padx=6, pady=4)

        mapping_box = ttk.LabelFrame(self, text="Разметка колонок файла")
        mapping_box.pack(fill="x", padx=4, pady=4)
        for c in range(8):
            mapping_box.columnconfigure(c, weight=1)

        targets = list(marketchain.CANONICAL_COLUMNS) if marketchain is not None else [
            "Ticker", "Expiry Date", "Strike", "Option Type", "Bid", "Ask", "Last", "Market Price",
            "Volume", "Open Interest", "Underlying Price", "Sigma",
        ]
        for i, target in enumerate(targets):
            r = i // 4
            c = (i % 4) * 2
            ttk.Label(mapping_box, text=f"{target}:").grid(row=r, column=c, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value="")
            cb = ttk.Combobox(mapping_box, textvariable=var, values=[""], state="readonly", width=22)
            cb.grid(row=r, column=c + 1, sticky="we", padx=4, pady=2)
            self.mapping_vars[target] = var

        tables = ttk.PanedWindow(self, orient="vertical")
        tables.pack(fill="both", expand=True, padx=4, pady=4)
        raw_box = ttk.LabelFrame(tables, text="Raw preview")
        norm_box = ttk.LabelFrame(tables, text="Normalized preview — данные, которые можно отправить в Vol Surface / Option Strategy")
        tables.add(raw_box, weight=1)
        tables.add(norm_box, weight=2)

        self.raw_tree = self._make_tree(raw_box, ("No data",), height=7)
        self.norm_tree = self._make_tree(norm_box, self.PREVIEW_COLUMNS, height=11)
        self.norm_tree.tag_configure("status_ok", background="#DFF2BF")
        self.norm_tree.tag_configure("status_error", background="#FFD2D2")

        self.info = ttk.Label(self, text="Загрузи Excel/CSV или сохрани шаблон. После разметки можно отправить данные в Vol Surface или Option Strategy.", foreground="#555")
        self.info.pack(anchor="w", padx=6, pady=2)

    def _make_tree(self, parent, columns, height=8):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self._set_tree_columns(tree, columns)
        return tree

    def _set_tree_columns(self, tree, columns):
        columns = tuple(str(c) for c in columns)
        tree.configure(columns=columns)
        for col in columns:
            tree.heading(col, text=col)
            width = 145 if col in ("Ticker", "Expiry Date", "Underlying Price", "Open Interest") else 110
            if col == "Status":
                width = 250
            tree.column(col, width=width, anchor="center", stretch=True)

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _fill_tree(self, tree, df: pd.DataFrame, columns=None, max_rows: int = 500):
        if df is None:
            df = pd.DataFrame()
        if columns is None:
            columns = list(df.columns) if not df.empty else ["No data"]
        self._set_tree_columns(tree, columns)
        self._clear_tree(tree)
        if df.empty:
            return
        view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows)
        for _, row in view.iterrows():
            values = []
            for col in columns:
                value = row.get(col, "")
                if isinstance(value, float):
                    value = "" if pd.isna(value) else f"{value:.6g}"
                elif pd.isna(value):
                    value = ""
                values.append(value)
            status = str(row.get("Status", ""))
            tag = "status_error" if status.startswith("ERROR") else "status_ok" if status == "OK" else ""
            try:
                tree.insert("", "end", values=values, tags=(tag,))
            except tk.TclError:
                tree.insert("", "end", values=values)

    def _load_file(self):
        try:
            path = filedialog.askopenfilename(
                title="Загрузить market chain Excel/CSV",
                filetypes=[("Market chain", "*.xlsx *.xls *.csv"), ("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not path:
                return
            self.raw_df = marketchain.load_market_chain(path)
            self._fill_tree(self.raw_tree, self.raw_df, columns=list(self.raw_df.columns), max_rows=200)
            mapping = marketchain.auto_mapping(self.raw_df.columns)
            values = [""] + list(self.raw_df.columns)
            for target, var in self.mapping_vars.items():
                cb = None

                var.set(mapping.get(target, ""))
            for child in self.winfo_children():
                pass
            self._refresh_mapping_combobox_values(values)
            self._apply_mapping()
            self.info.configure(text=f"Загружен файл: {Path(path).name}. Строк: {len(self.raw_df)}. Авторазметка применена.")
        except Exception as e:
            show_error("Ошибка загрузки market chain", e)

    def _refresh_mapping_combobox_values(self, values):
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):

                    child_var_name = str(child.cget("textvariable"))
                    if any(str(v) == child_var_name for v in self.mapping_vars.values()):
                        child.configure(values=values)
                walk(child)
        walk(self)

    def _save_template(self):
        try:
            path = filedialog.asksaveasfilename(
                title="Сохранить шаблон Market Chain",
                defaultextension=".xlsx",
                filetypes=[("Excel template", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not path:
                return
            marketchain.save_market_chain_template(path)
            self.info.configure(text=f"Шаблон сохранён: {path}")
        except Exception as e:
            show_error("Ошибка сохранения шаблона", e)

    def _mapping_from_ui(self):
        return {target: var.get() for target, var in self.mapping_vars.items()}

    def _apply_mapping(self):
        try:
            if self.raw_df is None or self.raw_df.empty:
                raise ValueError("Сначала загрузи Excel/CSV файл")
            self.normalized_df = marketchain.standardize_market_chain(self.raw_df, self._mapping_from_ui())
            self._fill_tree(self.norm_tree, self.normalized_df, columns=self.PREVIEW_COLUMNS, max_rows=500)
            ok_count = int((self.normalized_df["Status"].astype(str) == "OK").sum())
            err_count = int(self.normalized_df["Status"].astype(str).str.startswith("ERROR").sum())
            self.info.configure(text=f"Разметка применена. OK={ok_count}, errors={err_count}. Market Price = Market Price -> Mid(Bid/Ask) -> Last -> Bid -> Ask.")
        except Exception as e:
            show_error("Ошибка разметки market chain", e)

    def _ensure_normalized(self):
        if self.normalized_df is None or self.normalized_df.empty:
            self._apply_mapping()
        if self.normalized_df is None or self.normalized_df.empty:
            raise ValueError("Нет нормализованных данных")
        return self.normalized_df

    def _export_normalized(self):
        try:
            df = self._ensure_normalized()
            path = filedialog.asksaveasfilename(
                title="Экспорт нормализованного market chain",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not path:
                return
            suffix = Path(path).suffix.lower()
            if suffix == ".csv":
                df.to_csv(path, index=False)
            else:
                df.to_excel(path, index=False)
            self.info.configure(text=f"Нормализованный файл сохранён: {path}")
        except Exception as e:
            show_error("Ошибка экспорта нормализованного файла", e)

    def _send_to_vol_surface(self, calculate: bool = False):
        try:
            df = self._ensure_normalized()
            vol_df = marketchain.prepare_vol_surface_data(df)
            tab = self.vol_surface_tab
            if tab is None:
                raise ValueError("Vol Surface tab недоступна")
            tab._clear_tree(tab.input_tree)
            for _, row in vol_df.iterrows():
                tab.input_tree.insert("", "end", values=(
                    str(row.get("Ticker", "")),
                    f"{float(row['Strike']):g}",
                    str(row["Expiry Date"]),
                    f"{float(row['Market Price']):g}",
                    str(row["Option Type"]),
                ))
            try:
                tab.asset_cb.set(self.asset_type.get())
                tab.option_style_cb.set(self.option_style.get())
                tab._update_fields()
            except Exception:
                pass
            underlying = marketchain.first_underlying_price(df)
            if self.set_underlying_var.get() and underlying is not None:
                tab.S.set(f"{underlying:g}")
            tab.result_df = pd.DataFrame()
            tab._clear_tree(tab.output_tree)
            tab._update_expiry_combo(pd.DataFrame(columns=tab.OUTPUT_COLUMNS))
            tab._mark_calculation_pending()
            if calculate:
                tab._calculate()
                self.info.configure(text=f"Отправлено в Vol Surface и запущен расчёт: {len(vol_df)} строк.")
            else:
                tab.info.configure(text=f"Из Market Chain загружено {len(vol_df)} строк. Нажми 'Рассчитать implied vols'.")
                self.info.configure(text=f"Отправлено в Vol Surface: {len(vol_df)} строк.")
        except Exception as e:
            show_error("Ошибка отправки в Vol Surface", e)

    def _send_to_strategy(self):
        try:
            df = self._ensure_normalized()
            legs = marketchain.prepare_strategy_legs(
                df,
                side=self.strategy_side.get(),
                quantity=parse_float(self.strategy_qty.get(), "Qty"),
                style=self.option_style.get(),
                asset_type=self.asset_type.get(),
                sigma_source="Fixed sigma" if self.sigma_mode.get().startswith("Fixed") else "Sigma",
                fixed_sigma=parse_float(self.fixed_sigma.get(), "Fixed sigma"),
            )
            tab = self.strategy_tab
            if tab is None:
                raise ValueError("Option Strategy tab недоступна")
            if self.strategy_import_mode.get() == "Replace":
                tab._clear_tree(tab.input_tree)
                tab._clear_tree(tab.output_tree)
                tab.strategy_result = None
                write_result(tab.summary, "")
            for _, row in legs.iterrows():
                values = [row.get(col, "") for col in tab.INPUT_COLUMNS]
                tab.input_tree.insert("", "end", values=values)
            underlying = marketchain.first_underlying_price(df)
            if self.set_underlying_var.get() and underlying is not None:
                tab.S.set(f"{underlying:g}")
            if hasattr(tab, "_mark_strategy_pending"):
                tab._mark_strategy_pending()
            tab.info.configure(text=f"Из Market Chain добавлено {len(legs)} опционных ног. Нажми 'Рассчитать стратегию'.")
            self.info.configure(text=f"Отправлено в Option Strategy: {len(legs)} ног ({self.strategy_import_mode.get()}).")
        except Exception as e:
            show_error("Ошибка отправки в Option Strategy", e)


class OptionStrategyTab(ttk.Frame):

    INPUT_COLUMNS = tuple(strat.STRATEGY_COLUMNS if strat is not None else [
        "Instrument", "Side", "Option Type", "Quantity", "Strike", "Expiry Date",
        "Premium", "Sigma", "Style", "Asset Type",
    ])
    OUTPUT_COLUMNS = tuple(strat.LEG_RESULT_COLUMNS if strat is not None else [
        "Instrument", "Side", "Option Type", "Quantity", "Strike", "Expiry Date",
        "Premium", "Sigma", "Style", "Asset Type", "T", "Model Price", "Leg Value",
        "Delta", "Gamma", "Vega", "Theta", "Rho", "Status",
    ])

    def __init__(self, parent):
        super().__init__(parent, padding=8)
        self.strategy_result = None
        self._mpl_cursors = []

        common = ttk.LabelFrame(self, text="Общие параметры стратегии")
        common.pack(fill="x", padx=4, pady=4)
        for col in range(3):
            common.columnconfigure(col, weight=1)

        self.S = LabeledEntry(common, 0, "S current:", default="62.16")
        self.Rd = LabeledEntry(common, 1, "Rd:", default="0.0425")
        self.Rf = LabeledEntry(common, 2, "Rf:", default="0.025")
        self.q = LabeledEntry(common, 3, "q:", default="0.0")
        self.val_date = LabeledEntry(common, 4, "Valuation Date:", default=datetime.today().strftime("%Y-%m-%d"), hint="YYYY-MM-DD")
        self.multiplier = LabeledEntry(common, 5, "Contract multiplier:", default="1")
        self.n_steps = LabeledEntry(common, 6, "N steps tree:", default="200")
        self.s_min = LabeledEntry(common, 7, "S min graph:", default="0")
        self.s_max = LabeledEntry(common, 8, "S max graph:", default="130")
        self.n_points = LabeledEntry(common, 9, "Graph points:", default="121")

        row_frame = ttk.LabelFrame(self, text="Добавление ноги стратегии")
        row_frame.pack(fill="x", padx=4, pady=4)
        for col in range(10):
            row_frame.columnconfigure(col, weight=1)

        ttk.Label(row_frame, text="Instrument").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.row_instrument = tk.StringVar(value="Option")
        self.row_instrument_combo = ttk.Combobox(row_frame, textvariable=self.row_instrument,
                                                 values=["Option", "Future", "Spot"], state="readonly", width=10)
        self.row_instrument_combo.grid(row=0, column=1, sticky="we", padx=4, pady=2)
        self.row_instrument_combo.bind("<<ComboboxSelected>>", lambda e: self._update_leg_entry_states())

        ttk.Label(row_frame, text="Side").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.row_side = tk.StringVar(value="Buy")
        ttk.Combobox(row_frame, textvariable=self.row_side, values=["Buy", "Sell"], state="readonly", width=8).grid(row=0, column=3, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Option Type").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        self.row_option_type = tk.StringVar(value="Call")
        self.row_option_type_combo = ttk.Combobox(row_frame, textvariable=self.row_option_type, values=["Call", "Put"], state="readonly", width=8)
        self.row_option_type_combo.grid(row=0, column=5, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Qty").grid(row=0, column=6, sticky="w", padx=4, pady=2)
        self.row_qty = tk.StringVar(value="1")
        ttk.Entry(row_frame, textvariable=self.row_qty, width=8).grid(row=0, column=7, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Strike / Entry").grid(row=0, column=8, sticky="w", padx=4, pady=2)
        self.row_strike = tk.StringVar(value="60")
        ttk.Entry(row_frame, textvariable=self.row_strike, width=10).grid(row=0, column=9, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Expiry Date").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.row_expiry = tk.StringVar(value="2026-09-01")
        self.row_expiry_entry = ttk.Entry(row_frame, textvariable=self.row_expiry, width=12)
        self.row_expiry_entry.grid(row=1, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Premium / Entry").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        self.row_premium = tk.StringVar(value="5.10")
        ttk.Entry(row_frame, textvariable=self.row_premium, width=10).grid(row=1, column=3, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Sigma").grid(row=1, column=4, sticky="w", padx=4, pady=2)
        self.row_sigma = tk.StringVar(value="0.24")
        self.row_sigma_entry = ttk.Entry(row_frame, textvariable=self.row_sigma, width=10)
        self.row_sigma_entry.grid(row=1, column=5, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Style").grid(row=1, column=6, sticky="w", padx=4, pady=2)
        self.row_style = tk.StringVar(value="European")
        self.row_style_combo = ttk.Combobox(row_frame, textvariable=self.row_style, values=["European", "American"], state="readonly", width=10)
        self.row_style_combo.grid(row=1, column=7, sticky="we", padx=4, pady=2)

        ttk.Label(row_frame, text="Asset Type").grid(row=1, column=8, sticky="w", padx=4, pady=2)
        self.row_asset_type = tk.StringVar(value="Equity")
        ttk.Combobox(row_frame, textvariable=self.row_asset_type,
                     values=["Equity", "Index", "FX", "Commodity"], state="readonly", width=12).grid(row=1, column=9, sticky="we", padx=4, pady=2)

        btns = ttk.Frame(row_frame)
        btns.grid(row=2, column=0, columnspan=10, sticky="w", padx=4, pady=4)
        ttk.Button(btns, text="Добавить ногу", command=self._add_leg).pack(side="left", padx=2)
        ttk.Button(btns, text="Удалить ногу", command=self._delete_selected_legs).pack(side="left", padx=2)
        ttk.Button(btns, text="Очистить стратегию", command=self._clear_legs).pack(side="left", padx=2)
        self.strategy_calc_button = tk.Button(
            btns,
            text="Рассчитать стратегию",
            command=self._calculate_strategy,
            bg="#28a745",
            fg="white",
            activebackground="#218838",
            activeforeground="white",
            relief="raised",
            padx=10,
        )
        self.strategy_calc_button.pack(side="left", padx=10)
        ttk.Button(btns, text="Экспорт в Excel", command=self._export_excel).pack(side="left", padx=2)
        ttk.Button(btns, text="Сохранить стратегию", command=self._save_strategy).pack(side="left", padx=2)
        ttk.Button(btns, text="Загрузить стратегию", command=self._load_strategy).pack(side="left", padx=2)

        tables = ttk.PanedWindow(self, orient="horizontal")
        tables.pack(fill="x", expand=False, padx=4, pady=4)
        input_box = ttk.LabelFrame(tables, text="Ноги стратегии")
        output_box = ttk.LabelFrame(tables, text="Результаты по ногам")
        tables.add(input_box, weight=1)
        tables.add(output_box, weight=1)

        self.input_tree = self._make_tree(input_box, self.INPUT_COLUMNS, height=5)
        self.output_tree = self._make_tree(output_box, self.OUTPUT_COLUMNS, height=5)
        self.output_tree.tag_configure("status_ok", background="#DFF2BF")
        self.output_tree.tag_configure("status_error", background="#FFD2D2")

        bottom = ttk.PanedWindow(self, orient="horizontal")
        bottom.pack(fill="both", expand=True, padx=4, pady=4)

        summary_box = ttk.LabelFrame(bottom, text="Strategy Summary")
        plot_box = ttk.LabelFrame(bottom, text="Графики стратегии")
        bottom.add(summary_box, weight=1)
        bottom.add(plot_box, weight=3)

        self.summary = make_result_box(summary_box)
        self.summary.pack(fill="both", expand=True, padx=4, pady=4)


        risk_controls = ttk.LabelFrame(plot_box, text="Risk Matrix HTML — Spot × Volatility")
        risk_controls.pack(fill="x", padx=4, pady=(2, 4))
        value_values = list(strat.RISK_MATRIX_VALUE_METRICS) if strat is not None and hasattr(strat, "RISK_MATRIX_VALUE_METRICS") else ["Total P/L Today", "P/L at Expiry", "Strategy Price"]
        self.risk_row_factor = tk.StringVar(value="S")
        self.risk_col_factor = tk.StringVar(value="Volatility")
        self.risk_value_metric = tk.StringVar(value="Total P/L Today")
        self.risk_row_values = tk.StringVar(value="40,50,55,60,65,70,75,85")
        self.risk_col_values = tk.StringVar(value="0.10,0.15,0.20,0.22,0.26,0.30,0.35,0.40")

        ttk.Label(risk_controls, text="Spot rows:").pack(side="left", padx=(4, 2))
        ttk.Entry(risk_controls, textvariable=self.risk_row_values, width=34).pack(side="left", padx=2)
        ttk.Label(risk_controls, text="Vol columns:").pack(side="left", padx=(10, 2))
        ttk.Entry(risk_controls, textvariable=self.risk_col_values, width=34).pack(side="left", padx=2)
        ttk.Label(risk_controls, text="Value:").pack(side="left", padx=(10, 2))
        ttk.Combobox(risk_controls, textvariable=self.risk_value_metric, values=value_values, state="readonly", width=18).pack(side="left", padx=2)
        self.risk_matrix_button = tk.Button(
            risk_controls,
            text="Построить risk matrix HTML",
            command=lambda: self._calculate_risk_matrix(silent=False),
            bg="#28a745",
            fg="white",
            activebackground="#218838",
            activeforeground="white",
            relief="raised",
            padx=10,
        )
        self.risk_matrix_button.pack(side="left", padx=8)
        ttk.Label(risk_controls, text="Vol можно вводить как 0.20 или 20", foreground="#777").pack(side="left", padx=(6, 2))

        plot_controls = ttk.Frame(plot_box)
        plot_controls.pack(fill="x", padx=4, pady=3)

        ttk.Label(plot_controls, text="Библиотека:").pack(side="left", padx=4)
        self.chart_lib = tk.StringVar(value="Matplotlib (встроенный)")
        ttk.Combobox(plot_controls, textvariable=self.chart_lib, values=["Matplotlib (встроенный)", "Plotly"],
                     state="readonly", width=22).pack(side="left", padx=4)

        ttk.Label(plot_controls, text="Plotly output:").pack(side="left", padx=(12, 4))
        self.plotly_output = tk.StringVar(value="HTML")
        ttk.Combobox(plot_controls, textvariable=self.plotly_output, values=["HTML", "PNG"], state="readonly", width=8).pack(side="left", padx=4)

        ttk.Button(plot_controls, text="P/L at expiry", command=lambda: self._plot_profile("P/L at Expiry")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Value today", command=lambda: self._plot_profile("Strategy Value Today")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Delta", command=lambda: self._plot_profile("Delta")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Gamma", command=lambda: self._plot_profile("Gamma")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Vega", command=lambda: self._plot_profile("Vega")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Theta", command=lambda: self._plot_profile("Theta")).pack(side="left", padx=3)
        ttk.Button(plot_controls, text="Rho", command=lambda: self._plot_profile("Rho")).pack(side="left", padx=3)
        tk.Button(plot_controls, text="Очистить график", command=self._clear_strategy_plot,
                  bg="#ffcc00", fg="black", activebackground="#e6b800", relief="raised").pack(side="left", padx=8)

        self.fig = Figure(figsize=(9, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_box)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_box)
        self.toolbar.update()

        self.info = ttk.Label(self, text="Option Strategy: расчёты находятся в option_strategy.py. Поддержаны Option / Future / Spot.", foreground="#555")
        self.info.pack(anchor="w", padx=6, pady=2)

        self._insert_demo_strategy()
        self._update_leg_entry_states()
        self._bind_strategy_recalc_triggers()
        self._mark_strategy_pending()
        self._mark_risk_matrix_pending()

    def _mark_strategy_pending(self, *_):
        if hasattr(self, "strategy_calc_button"):
            set_action_button_state(self.strategy_calc_button, pending=True)
        self._mark_risk_matrix_pending()

    def _mark_strategy_done(self):
        if hasattr(self, "strategy_calc_button"):
            set_action_button_state(self.strategy_calc_button, pending=False)

    def _mark_risk_matrix_pending(self, *_):
        if hasattr(self, "risk_matrix_button"):
            set_action_button_state(self.risk_matrix_button, pending=True)

    def _mark_risk_matrix_done(self):
        if hasattr(self, "risk_matrix_button"):
            set_action_button_state(self.risk_matrix_button, pending=False)

    def _bind_strategy_recalc_triggers(self):
        entries = [
            self.S.entry, self.Rd.entry, self.Rf.entry, self.q.entry, self.val_date.entry,
            self.multiplier.entry, self.n_steps.entry, self.s_min.entry, self.s_max.entry, self.n_points.entry,
        ]
        for entry in entries:
            entry.bind("<KeyRelease>", self._mark_strategy_pending, add="+")

        row_vars = [
            self.row_instrument, self.row_side, self.row_option_type, self.row_qty, self.row_strike,
            self.row_expiry, self.row_premium, self.row_sigma, self.row_style, self.row_asset_type,
        ]
        for var in row_vars:
            try:
                var.trace_add("write", self._mark_strategy_pending)
            except Exception:
                pass

        risk_vars = [self.risk_row_values, self.risk_col_values, self.risk_value_metric]
        for var in risk_vars:
            try:
                var.trace_add("write", self._mark_risk_matrix_pending)
            except Exception:
                pass

    def _make_tree(self, parent, columns, height=8):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        for col in columns:
            tree.heading(col, text=col)
            if col in ("Status",):
                width = 260
            elif col in ("Expiry Date", "Asset Type", "Option Type", "Instrument"):
                width = 115
            else:
                width = 100
            tree.column(col, width=width, anchor="center", stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def _update_leg_entry_states(self):
        instrument = self.row_instrument.get()
        if instrument == "Option":
            self.row_option_type_combo.configure(state="readonly")
            self.row_sigma_entry.configure(state="normal")
            self.row_style_combo.configure(state="readonly")
            self.row_expiry_entry.configure(state="normal")
        elif instrument == "Future":
            self.row_option_type_combo.configure(state="disabled")
            self.row_sigma_entry.configure(state="disabled")
            self.row_style_combo.configure(state="disabled")
            self.row_expiry_entry.configure(state="normal")
        else:
            self.row_option_type_combo.configure(state="disabled")
            self.row_sigma_entry.configure(state="disabled")
            self.row_style_combo.configure(state="disabled")
            self.row_expiry_entry.configure(state="disabled")

    def _insert_demo_strategy(self):
        demo_rows = [
            ("Option", "Buy", "Call", "1", "60", "2026-09-01", "5.10", "0.24", "European", "Equity"),
            ("Option", "Sell", "Call", "1", "70", "2026-09-01", "1.80", "0.24", "European", "Equity"),
            ("Option", "Buy", "Put", "1", "55", "2026-09-01", "2.20", "0.26", "European", "Equity"),
            ("Spot", "Buy", "", "1", "", "", "62.16", "", "", "Equity"),
        ]
        for row in demo_rows:
            self.input_tree.insert("", "end", values=row)

    def _add_leg(self):
        try:
            values = (
                self.row_instrument.get(),
                self.row_side.get(),
                self.row_option_type.get() if self.row_instrument.get() == "Option" else "",
                self.row_qty.get().strip(),
                self.row_strike.get().strip(),
                self.row_expiry.get().strip() if self.row_instrument.get() != "Spot" else "",
                self.row_premium.get().strip(),
                self.row_sigma.get().strip() if self.row_instrument.get() == "Option" else "",
                self.row_style.get() if self.row_instrument.get() == "Option" else "",
                self.row_asset_type.get(),
            )
            self.input_tree.insert("", "end", values=values)
            self.strategy_result = None
            self._mark_strategy_pending()
            self.info.configure(text="Нога добавлена. Нажми 'Рассчитать стратегию'.")
        except Exception as e:
            show_error("Ошибка добавления ноги", e)

    def _delete_selected_legs(self):
        for item in self.input_tree.selection():
            self.input_tree.delete(item)
        self.strategy_result = None
        self._clear_tree(self.output_tree)
        self._mark_strategy_pending()

    def _clear_legs(self):
        self._clear_tree(self.input_tree)
        self._clear_tree(self.output_tree)
        self.strategy_result = None
        write_result(self.summary, "")
        self.ax.clear()
        self.canvas.draw()
        self._mark_strategy_pending()
        self.info.configure(text="Стратегия очищена")

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _tree_to_dataframe(self):
        rows = []
        for item in self.input_tree.get_children():
            values = self.input_tree.item(item, "values")
            if values:
                rows.append(dict(zip(self.INPUT_COLUMNS, values)))
        if not rows:
            raise ValueError("Стратегия пустая")
        return pd.DataFrame(rows)

    def _common_params(self):
        return {
            "S": self.S.get(),
            "Rd": self.Rd.get(),
            "Rf": self.Rf.get(),
            "q": self.q.get(),
            "Valuation Date": self.val_date.get(),
            "Contract multiplier": self.multiplier.get(),
            "N steps": self.n_steps.get(),
            "S min graph": self.s_min.get(),
            "S max graph": self.s_max.get(),
            "Graph points": self.n_points.get(),
            "Risk row factor": self.risk_row_factor.get() if hasattr(self, "risk_row_factor") else "S",
            "Risk row values": self.risk_row_values.get() if hasattr(self, "risk_row_values") else "",
            "Risk column factor": self.risk_col_factor.get() if hasattr(self, "risk_col_factor") else "Volatility",
            "Risk column values": self.risk_col_values.get() if hasattr(self, "risk_col_values") else "",
            "Risk value metric": self.risk_value_metric.get() if hasattr(self, "risk_value_metric") else "Total P/L Today",
        }

    def _apply_common_params(self, params):
        mapping = {
            "S": self.S,
            "Rd": self.Rd,
            "Rf": self.Rf,
            "q": self.q,
            "Valuation Date": self.val_date,
            "Contract multiplier": self.multiplier,
            "N steps": self.n_steps,
            "S min graph": self.s_min,
            "S max graph": self.s_max,
            "Graph points": self.n_points,
            "Risk row factor": self.risk_row_factor,
            "Risk row values": self.risk_row_values,
            "Risk column factor": self.risk_col_factor,
            "Risk column values": self.risk_col_values,
            "Risk value metric": self.risk_value_metric,
        }
        for key, entry in mapping.items():
            if key in params:
                entry.set(params[key])

    def _calculate_strategy(self):
        try:
            legs = self._tree_to_dataframe()
            result = strat.evaluate_strategy(
                legs,
                S=parse_float(self.S.get(), "S current"),
                Rd=parse_float(self.Rd.get(), "Rd"),
                Rf=parse_float(self.Rf.get(), "Rf"),
                q=parse_float(self.q.get(), "q"),
                valuation_date=parse_date(self.val_date.get(), "Valuation Date"),
                contract_multiplier=parse_float(self.multiplier.get(), "Contract multiplier"),
                pricing_module=pricing,
                vol_surface_module=volsurf,
                n_steps=parse_int(self.n_steps.get(), "N steps"),
                s_min=parse_float(self.s_min.get(), "S min graph"),
                s_max=parse_float(self.s_max.get(), "S max graph"),
                n_points=parse_int(self.n_points.get(), "Graph points"),
            )
            self.strategy_result = result
            self._fill_output_tree(result["legs"])
            self._fill_summary(result["summary"])
            self._plot_profile("P/L at Expiry", silent=True)
            ok_count = int((result["legs"]["Status"].astype(str) == "OK").sum())
            err_count = int(result["legs"]["Status"].astype(str).str.startswith("ERROR").sum())
            self._mark_strategy_done()
            self.info.configure(text=f"Стратегия рассчитана: OK={ok_count}, errors={err_count}. Профили построены по {len(result['profiles'])} точкам S.")
        except Exception as e:
            show_error("Ошибка расчёта стратегии", e)

    def _fill_output_tree(self, df: pd.DataFrame):
        self._clear_tree(self.output_tree)
        for _, row in df.iterrows():
            values = []
            for col in self.OUTPUT_COLUMNS:
                value = row.get(col, "")
                if isinstance(value, float):
                    if pd.isna(value):
                        value = ""
                    elif col in ("T", "Model Price", "Leg Value", "Delta", "Gamma", "Vega", "Theta", "Rho"):
                        value = f"{value:.6f}"
                    else:
                        value = f"{value:g}"
                values.append(value)
            status = str(row.get("Status", ""))
            tag = "status_error" if status.startswith("ERROR") else "status_ok"
            self.output_tree.insert("", "end", values=values, tags=(tag,))

    def _fill_summary(self, summary: dict):
        lines = []
        for key, value in summary.items():
            if isinstance(value, list):
                text = ", ".join(f"{x:.6f}" for x in value) if value else "—"
            elif isinstance(value, float):
                text = f"{value:.6f}"
            else:
                text = str(value)
            lines.append(f"{key:<24}: {text}")
        write_result(self.summary, "\n".join(lines))

    def _plot_profile(self, column: str, silent: bool = False):
        try:
            if self.strategy_result is None:
                self._calculate_strategy()
                if self.strategy_result is None:
                    return
            profiles = self.strategy_result["profiles"]
            if column not in profiles.columns:
                raise ValueError(f"Нет профиля {column}")
            if self.chart_lib.get().startswith("Plotly") and not silent:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=profiles["S"],
                    y=profiles[column],
                    mode="lines",
                    name=column,
                    hovertemplate="S: %{x:.6f}<br>" + column + ": %{y:.6f}<extra></extra>",
                ))
                fig.update_layout(
                    title=f"Option Strategy — {column}",
                    xaxis_title="Underlying price S",
                    yaxis_title=column,
                    template="plotly_white",
                    hovermode="closest",
                )
                path = open_plotly_figure(fig, f"option_strategy_{column.lower().replace(' ', '_').replace('/', '_')}", self.plotly_output.get())
                self.info.configure(text=f"Открыт Plotly график: {path.name}")
                return

            self.ax.clear()
            line, = self.ax.plot(profiles["S"], profiles[column], linewidth=2)
            if column == "P/L at Expiry":
                self.ax.axhline(0, linestyle="--", linewidth=1)
            self.ax.set_title(f"Option Strategy — {column}")
            self.ax.set_xlabel("Underlying price S")
            self.ax.set_ylabel(column)
            self.ax.grid(True, alpha=0.4)
            labels = [f"S: {s:.6f}\n{column}: {y:.6f}" for s, y in zip(profiles["S"], profiles[column])]
            self._mpl_cursors = []
            cursor = add_mpl_hover(line, labels)
            if cursor is not None:
                self._mpl_cursors.append(cursor)
            self.fig.tight_layout()
            self.canvas.draw()
            if not silent:
                self.info.configure(text=f"Построен график: {column}")
        except Exception as e:
            show_error("Ошибка построения графика стратегии", e)


    def _clear_strategy_plot(self):

        try:
            self.fig.clear()
            self.ax = self.fig.add_subplot(111)
            self.ax.set_title("График стратегии очищен")
            self.ax.grid(True, alpha=0.25)
            self._mpl_cursors = []
            self.fig.tight_layout()
            self.canvas.draw()
            self.info.configure(text="Matplotlib-график стратегии очищен.")
        except Exception as e:
            show_error("Ошибка очистки графика стратегии", e)


    def _parse_float_levels(self, text: str, name: str) -> list[float]:
        raw = str(text).replace(";", ",").strip()
        if not raw:
            raise ValueError(f"Поле {name!r} пустое")
        values = []
        for token in raw.split(","):
            token = token.strip().replace(" ", "")
            if not token:
                continue
            values.append(float(token))
        if not values:
            raise ValueError(f"В поле {name!r} нет чисел")
        return values

    def _calculate_risk_matrix(self, silent: bool = False):
        try:
            legs = self._tree_to_dataframe()
            risk = strat.calculate_two_factor_risk_matrix(
                legs,
                row_factor=self.risk_row_factor.get(),
                row_values=self._parse_float_levels(self.risk_row_values.get(), "row values"),
                col_factor=self.risk_col_factor.get(),
                col_values=self._parse_float_levels(self.risk_col_values.get(), "column values"),
                value_metric=self.risk_value_metric.get(),
                S=parse_float(self.S.get(), "S current"),
                Rd=parse_float(self.Rd.get(), "Rd"),
                Rf=parse_float(self.Rf.get(), "Rf"),
                q=parse_float(self.q.get(), "q"),
                valuation_date=parse_date(self.val_date.get(), "Valuation Date"),
                contract_multiplier=parse_float(self.multiplier.get(), "Contract multiplier"),
                pricing_module=pricing,
                vol_surface_module=volsurf,
                n_steps=parse_int(self.n_steps.get(), "N steps"),
                s_min=parse_float(self.s_min.get(), "S min graph"),
                s_max=parse_float(self.s_max.get(), "S max graph"),
                n_points=parse_int(self.n_points.get(), "Graph points"),
            )
            if self.strategy_result is None:
                self.strategy_result = {}
            self.strategy_result["risk_matrix"] = risk
            if not silent:
                self._open_risk_matrix_html(risk)
                self._mark_risk_matrix_done()
                self.info.configure(
                    text=f"Risk matrix открыта в HTML: {risk.get('row_factor')} × {risk.get('col_factor')}, value={risk.get('value_metric')}."
                )
            return risk
        except Exception as e:
            if not silent:
                show_error("Ошибка построения risk matrix", e)
            else:
                self.info.configure(text=f"Risk matrix не построена: {e}")
            return None

    def _open_risk_matrix_html(self, risk: dict):
        matrix_raw = risk.get("matrix_raw")
        if matrix_raw is None or matrix_raw.empty:
            raise ValueError("Risk matrix пуста")
        z = matrix_raw.to_numpy(dtype=float)
        x_labels = [str(c) for c in matrix_raw.columns]
        y_labels = [str(i) for i in matrix_raw.index]
        text_labels = [["" if not np.isfinite(v) else f"{v:.4f}" for v in row] for row in z]
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            text=text_labels,
            texttemplate="%{text}",
            hovertemplate=(
                f"{risk.get('col_factor')}: %{{x}}<br>"
                f"{risk.get('row_factor')}: %{{y}}<br>"
                f"{risk.get('value_metric')}: %{{z:.6f}}<extra></extra>"
            ),
            colorbar=dict(title=risk.get("value_metric", "P/L")),
        ))
        fig.update_layout(
            title=(
                f"Risk Matrix — {risk.get('value_metric', 'P/L')} "
                f"by {risk.get('row_factor')} × {risk.get('col_factor')}"
            ),
            xaxis_title=str(risk.get("col_factor", "Columns")),
            yaxis_title=str(risk.get("row_factor", "Rows")),
            template="plotly_white",
            height=760,
            width=1100,
        )
        open_plotly_figure(fig, "option_strategy_risk_matrix", "HTML")

    def _export_excel(self):
        try:
            if self.strategy_result is None:
                raise ValueError("Сначала рассчитай стратегию")
            if "risk_matrix" not in self.strategy_result:
                self._calculate_risk_matrix(silent=True)
            path = filedialog.asksaveasfilename(
                title="Экспорт стратегии в Excel",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            )
            if not path:
                return
            strat.export_to_excel(self.strategy_result, path)
            self.info.configure(text=f"Экспортировано в Excel: {path}")
        except Exception as e:
            show_error("Ошибка экспорта стратегии", e)

    def _save_strategy(self):
        try:
            legs = self._tree_to_dataframe()
            path = filedialog.asksaveasfilename(
                title="Сохранить стратегию",
                defaultextension=".json",
                filetypes=[("JSON strategy", "*.json"), ("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")],
            )
            if not path:
                return
            strat.save_strategy(legs, self._common_params(), path)
            self.info.configure(text=f"Стратегия сохранена: {path}")
        except Exception as e:
            show_error("Ошибка сохранения стратегии", e)

    def _load_strategy(self):
        try:
            path = filedialog.askopenfilename(
                title="Загрузить стратегию",
                filetypes=[("Strategy files", "*.json *.csv *.xlsx *.xls"), ("All files", "*.*")],
            )
            if not path:
                return
            data = strat.load_strategy(path)
            self._apply_common_params(data.get("common_params", {}))
            self._clear_tree(self.input_tree)
            legs = data["legs"]
            for _, row in legs.iterrows():
                values = [row.get(col, "") for col in self.INPUT_COLUMNS]
                self.input_tree.insert("", "end", values=values)
            self.strategy_result = None
            self._clear_tree(self.output_tree)
            write_result(self.summary, "")
            self._mark_strategy_pending()
            self.info.configure(text=f"Стратегия загружена: {path}")
        except Exception as e:
            show_error("Ошибка загрузки стратегии", e)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Derivatives Pricing GUI")
        self.state('zoomed')


        try:
            style = ttk.Style(self)
            style.theme_use("clam")
        except tk.TclError:
            pass

        if _import_error is not None:

            messagebox.showerror("Ошибка импорта исходных модулей",
                str(_import_error) +
                f"\n\nBASE_DIR = {BASE_DIR}\n"
                f"Проверь, что файлы\n  {PRICING_FILE}\n  {ZCYC_FILE}\n  {CAP_FILE}\n"
                f"лежат рядом с pricing_gui.py, или поправь имена в шапке файла.\n"
                f"Также нужны файлы: {VOL_FILE}, {STRATEGY_FILE}, {MARKET_FILE}, {RATES_FILE}")

            ttk.Label(self, text="Не удалось импортировать исходные модули. Закрой окно.",
                      padding=20).pack()
            return

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self.options_tab = OptionsTab(nb)
        self.vol_surface_tab = VolSurfaceTab(nb)
        self.option_strategy_tab = OptionStrategyTab(nb)
        self.market_chain_tab = MarketChainTab(
            nb,
            vol_surface_tab=self.vol_surface_tab,
            strategy_tab=self.option_strategy_tab,
        )

        nb.add(self.options_tab,          text="Options")
        nb.add(self.vol_surface_tab,      text="Vol Surface")
        nb.add(self.option_strategy_tab,  text="Option Strategy")
        nb.add(ForwardsTab(nb),           text="Forwards")
        nb.add(SwapTab(nb),               text="Swap IRS")
        nb.add(CapFloorTab(nb),           text="Cap / Floor")
        nb.add(ZCYCTab(nb),               text="ZCYC Curve RUB")
        nb.add(ExternalCurveTab(nb, "USD"), text="ZCYC Curve USD")
        nb.add(ExternalCurveTab(nb, "CNY"), text="ZCYC Curve CNY")
        nb.add(self.market_chain_tab,     text="Market Chain")


if __name__ == "__main__":
    app = App()
    app.mainloop()
