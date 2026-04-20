"""
pricing_gui.py
==============
Tkinter GUI-обёртка для существующих модулей:
    - pricing__2_.py                          (опционы, форварды, Swap_IRS)
    - zcyc_построить_на_конкретный_день.py    (ZCYCCurveLoader)
    - cap_floor_ruon.py                       (CapFloor_RUONIA)

Оригинальные файлы НЕ модифицируются — GUI их только импортирует и оборачивает.
Если имена файлов у тебя другие, поправь константы PRICING_FILE / ZCYC_FILE / CAP_FILE ниже.

Запуск:
    python pricing_gui.py

Зависимости: tkinter (стандартная), numpy, pandas, scipy, matplotlib, requests.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from datetime import datetime
import traceback

# matplotlib — TkAgg backend обязательно ДО pyplot, чтобы встроенный в Tk график работал корректно
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import pandas as pd

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext


# =============================================================================
# 1. ДИНАМИЧЕСКИЙ ИМПОРТ ИСХОДНЫХ МОДУЛЕЙ (без переименования файлов)
# =============================================================================

BASE_DIR = Path(__file__).parent

# Если у тебя другие имена файлов — правь здесь.
PRICING_FILE = "pricing__2_.py"
ZCYC_FILE    = "zcyc_построить_на_конкретный_день.py"
CAP_FILE     = "cap_floor_ruon.py"


def _load_module(filename: str, alias: str):
    """Загружает модуль из файла по пути, даже если имя с кириллицей / цифрами."""
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


# Отложим ошибки импорта до момента запуска GUI, чтобы показать их в messagebox,
# а не крашнуть процесс до создания окна.
_import_error = None
pricing = zcyc = capf = None
try:
    pricing = _load_module(PRICING_FILE, "pricing_src")
    zcyc    = _load_module(ZCYC_FILE,    "zcyc_src")
    capf    = _load_module(CAP_FILE,     "capfloor_src")
except Exception as e:
    _import_error = e


# =============================================================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ GUI
# =============================================================================

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


def parse_date(s: str, name: str) -> pd.Timestamp:
    s = s.strip()
    if s == "":
        raise ValueError(f"Поле '{name}' пустое")
    # допускаем и YYYY-MM-DD и DD.MM.YYYY
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    raise ValueError(f"Поле '{name}' не в формате YYYY-MM-DD: {s!r}")


def parse_list(s: str):
    """Парсит строку вида 'a, b, c' в список строк; пустая строка -> []."""
    s = s.strip()
    if s == "":
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def years_between(d_now: pd.Timestamp, d_exp: pd.Timestamp) -> float:
    return (d_exp - d_now) / pd.Timedelta(days=365)


class LabeledEntry:
    """
    Удобная обёртка: row с Label + Entry + tooltip-подсказкой.
    Возвращает сам Entry через .entry и умеет get()/set().
    """
    def __init__(self, parent, row, label, default="", width=18, hint=""):
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", padx=4, pady=2)
        self.var = tk.StringVar(value=str(default))
        self.entry = ttk.Entry(parent, textvariable=self.var, width=width)
        self.entry.grid(row=row, column=1, sticky="we", padx=4, pady=2)
        if hint:
            hint_lbl = ttk.Label(parent, text=hint, foreground="#777")
            hint_lbl.grid(row=row, column=2, sticky="w", padx=4, pady=2)

    def get(self): return self.var.get()
    def set(self, value): self.var.set(str(value))


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


# =============================================================================
# 3. ВКЛАДКА: OPTIONS (европейские + американские, Equity/Index/FX/Commodity)
# =============================================================================

class OptionsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        # --- блок выбора типа ---
        top = ttk.LabelFrame(self, text="Тип опциона")
        top.pack(fill="x", padx=4, pady=4)

        self.style_cb = LabeledCombo(top, 0, "Стиль:",
            ["European", "American"], default="European", on_change=self._update_fields)
        self.asset_cb = LabeledCombo(top, 1, "Базовый актив:",
            ["Equity", "Index", "FX", "Commodity"], default="Equity", on_change=self._update_fields)
        self.cp_cb = LabeledCombo(top, 2, "Call/Put:",
            ["Call", "Put"], default="Call")

        # --- параметры ---
        params = ttk.LabelFrame(self, text="Параметры")
        params.pack(fill="x", padx=4, pady=4)
        params.columnconfigure(1, weight=1)

        self.S  = LabeledEntry(params, 0, "S (спот):",        default="62.16")
        self.K  = LabeledEntry(params, 1, "K (страйк):",       default="60")
        self.dn = LabeledEntry(params, 2, "Дата оценки:",     default=datetime.today().strftime("%Y-%m-%d"), hint="YYYY-MM-DD")
        self.de = LabeledEntry(params, 3, "Дата экспирации:", default="2026-11-03",                          hint="YYYY-MM-DD")
        self.Rd = LabeledEntry(params, 4, "Rd (risk-free в кот. валюте):", default="0.0425")
        self.Rf = LabeledEntry(params, 5, "Rf (foreign risk-free):",       default="0.025")
        self.Sig = LabeledEntry(params, 6, "Sigma (vol):",    default="0.23809")
        self.q  = LabeledEntry(params, 7, "q (div yield):",    default="0.0")

        # --- параметры симуляций ---
        sim = ttk.LabelFrame(self, text="Симуляции / дерево")
        sim.pack(fill="x", padx=4, pady=4)
        sim.columnconfigure(1, weight=1)

        self.N_sim = LabeledEntry(sim, 0, "N_sim (Monte-Carlo / шагов бин. дерева):", default="5000")
        self.N_steps = LabeledEntry(sim, 1, "N_steps (шагов в году, для US):", default="100")
        self.Poly_degree = LabeledEntry(sim, 2, "Poly_degree (LSM):", default="3")
        self.seed = LabeledEntry(sim, 3, "seed:", default="42")

        # --- дивиденды (только US Equity/Index) ---
        self.div_frame = ttk.LabelFrame(self, text="Дивиденды (только American Equity/Index)")
        self.div_frame.pack(fill="x", padx=4, pady=4)
        self.div_frame.columnconfigure(1, weight=1)

        self.div_dates = LabeledEntry(self.div_frame, 0, "Даты дивов (через запятую):",
                                      default="", hint="пример: 2025-11-29, 2026-05-15")
        self.div_amount = LabeledEntry(self.div_frame, 1, "Суммы дивов (через запятую):",
                                       default="", hint="пример: 0.5, 0.6")

        # --- греки ---
        self.calc_greeks_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Рассчитать греки (numerical bump-and-reprice)",
                        variable=self.calc_greeks_var).pack(anchor="w", padx=8, pady=2)

        # --- кнопка + вывод ---
        ttk.Button(self, text="Рассчитать", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

        self._update_fields()

    # -------------------------------------------------------------------------
    def _update_fields(self):
        """Показываем/прячем поля в зависимости от выбранного типа."""
        style = self.style_cb.get()
        asset = self.asset_cb.get()

        # Rf имеет смысл для FX / Commodity (foreign rate либо convenience-подобный параметр)
        need_rf = asset in ("FX", "Commodity")
        for widget in (self.Rf.entry,):
            widget.configure(state="normal" if need_rf else "disabled")

        # Дивиденды — только American + Equity/Index
        if style == "American" and asset in ("Equity", "Index"):
            for child in self.div_frame.winfo_children():
                try: child.configure(state="normal")
                except tk.TclError: pass
        else:
            for child in self.div_frame.winfo_children():
                try: child.configure(state="disabled")
                except tk.TclError: pass

    # -------------------------------------------------------------------------
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
            q   = parse_float(self.q.get(),   "q")

            N_sim   = parse_int(self.N_sim.get(),   "N_sim")
            N_steps = parse_int(self.N_steps.get(), "N_steps")
            Poly_d  = parse_int(self.Poly_degree.get(), "Poly_degree")
            seed    = parse_int(self.seed.get(),    "seed")

            # --- выбираем нужный класс из pricing ---
            opt = None
            option_class = None

            if style == "European":
                if asset in ("Equity", "Index"):
                    option_class = pricing.EUR_S_EQ_option if asset == "Equity" else pricing.EUR_S_IND_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)
                else:  # FX / Commodity
                    option_class = pricing.EUR_F_FX_option if asset == "FX" else pricing.EUR_F_Commodity_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Rf=Rf, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)

            else:  # American
                if asset in ("Equity", "Index"):
                    # парсим дивы
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
                    # для FX/Commodity в исходнике американский опцион не реализован — fallback на европейский
                    option_class = pricing.EUR_F_FX_option if asset == "FX" else pricing.EUR_F_Commodity_option
                    opt = option_class(S=S, K=K, T=T, Rd=Rd, Rf=Rf, Sig=Sig, q=q,
                                       Option_type=cp, N_sim=N_sim, seed=seed)

            # --- считаем цену ---
            lines = []
            lines.append(f"Опцион: {asset}, {style}, {cp}")
            lines.append(f"T = {T:.6f} лет")
            lines.append("-" * 60)

            if style == "European" or asset in ("FX", "Commodity"):
                price_analytical = opt.Call_price() if cp == "Call" else opt.Put_price()
                lines.append(f"Analytical (закрытая формула):  {price_analytical:.6f}")
                price_mc = opt.Monte_carlo_sim()
                lines.append(f"Monte-Carlo (N={N_sim}):          {price_mc:.6f}")
            else:
                # American Equity/Index
                price_bin = opt.price()
                lines.append(f"Binomial tree:                    {price_bin:.6f}")
                price_mc = opt.Monte_carlo_sim()
                lines.append(f"LSM / Monte-Carlo (N={N_sim}):     {price_mc:.6f}")

            # --- греки ---
            if self.calc_greeks_var.get():
                lines.append("")
                lines.append("Greeks (numerical bump-and-reprice):")
                kwargs = dict(
                    option_class=option_class,
                    S=S, K=K, T=T, Rd=Rd, Sig=Sig,
                    q=q, Rf=Rf, Option_type=cp,
                    N_sim=N_sim, seed=seed,
                )
                if option_class is pricing.US_S_EQ_option:
                    kwargs.update(N_steps=N_steps, Poly_degree=Poly_d,
                                  div_dates=[parse_date(d, "dd") for d in parse_list(self.div_dates.get())],
                                  div_amounts=[float(x.replace(",", ".")) for x in parse_list(self.div_amount.get())],
                                  date_now=dn)
                greeks = pricing.calc_greeks(**kwargs)
                for g, v in greeks.items():
                    lines.append(f"  {g:<7} = {v:.6f}")

            write_result(self.result, "\n".join(lines))

        except Exception as e:
            show_error("Ошибка расчёта опциона", e)


# =============================================================================
# 4. ВКЛАДКА: FORWARDS
# =============================================================================

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

        self.comm_frame = comm  # для включения/отключения

        ttk.Button(self, text="Рассчитать форвардную цену", command=self._on_calculate).pack(pady=6)

        self.result = make_result_box(self)
        self.result.pack(fill="both", expand=True, padx=4, pady=4)

        self._update_fields()

    def _update_fields(self):
        asset = self.asset_cb.get()
        # Rf только для FX
        self.Rf.entry.configure(state="normal" if asset == "FX" else "disabled")
        # q только для Equity/Index
        self.q.entry.configure(state="normal" if asset == "Equity/Index" else "disabled")
        # commodity блок
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

            else:  # Commodity
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


# =============================================================================
# 5. ВКЛАДКА: SWAP IRS (MOEX zero curve)
# =============================================================================

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
            # проверим формат
            parse_date(date, "date")

            swap = pricing.Swap_IRS(T=T, freq=freq, notional=N, date=date)
            fixed = swap.price()

            # покажем также таблицу дат платежей
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


# =============================================================================
# 6. ВКЛАДКА: CAP / FLOOR НА RUONIA
# =============================================================================

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

            # Исходный класс ожидает option_type 'put'/'call' — в docstring автор приводит пример 'put' для floor.
            # Но внутри сравнение идёт с 'cap'/'floor'. Передаём напрямую как выбрано в комбо.
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


# =============================================================================
# 7. ВКЛАДКА: ZCYC CURVE (график встроен в окно)
# =============================================================================

class ZCYCTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=8)

        controls = ttk.LabelFrame(self, text="Параметры кривой")
        controls.pack(fill="x", padx=4, pady=4)
        controls.columnconfigure(1, weight=1)

        self.mode_cb = LabeledCombo(controls, 0, "Режим:",
            ["single", "week", "month", "year", "custom"], default="single",
            on_change=self._update_fields)

        self.base_date = LabeledEntry(controls, 1, "base_date:",
                                       default=datetime.today().strftime("%Y-%m-%d"),
                                       hint="для single/week/month/year")
        self.from_date = LabeledEntry(controls, 2, "from_date:",
                                       default="2026-03-10",
                                       hint="для custom")
        self.to_date   = LabeledEntry(controls, 3, "to_date:",
                                       default="2026-04-16",
                                       hint="для custom")
        self.lookback  = LabeledEntry(controls, 4, "max_lookback_days:", default="7")

        ttk.Button(self, text="Построить кривую", command=self._on_plot).pack(pady=6)

        # место под график
        self.plot_frame = ttk.Frame(self)
        self.plot_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax  = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()

        self.info = ttk.Label(self, text="", foreground="#555")
        self.info.pack(anchor="w", padx=6, pady=2)

        self._update_fields()

    def _update_fields(self):
        mode = self.mode_cb.get()
        is_custom = (mode == "custom")
        self.base_date.entry.configure(state="disabled" if is_custom else "normal")
        self.from_date.entry.configure(state="normal" if is_custom else "disabled")
        self.to_date.entry.configure(state="normal" if is_custom else "disabled")

    def _on_plot(self):
        try:
            mode = self.mode_cb.get()
            lookback = parse_int(self.lookback.get(), "max_lookback_days")

            loader = zcyc.ZCYCCurveLoader()

            if mode == "custom":
                from_d = self.from_date.get().strip()
                to_d   = self.to_date.get().strip()
                parse_date(from_d, "from_date")
                parse_date(to_d,   "to_date")
                dates = loader.get_custom_dates(from_d, to_d)
            else:
                bd = self.base_date.get().strip()
                parse_date(bd, "base_date")
                dates = loader.get_predefined_dates(bd, mode)

            curves = loader.get_curves_for_dates(dates, max_lookback_days=lookback, verbose=False)

            # Рендерим график на встроенный canvas (оригинальный plot_curves не трогаем —
            # он использует plt.show(), что в Tk mainloop неудобно).
            self.ax.clear()
            for curve_date, df in curves.items():
                df = df.sort_values("period")
                self.ax.plot(df["period"], df["value"], marker="o", label=str(curve_date))

            if mode == "single":
                title = f"ZCYC на {list(curves.keys())[0]}"
            elif mode == "custom":
                title = f"Сравнение кривых: {self.from_date.get()} vs {self.to_date.get()}"
            else:
                title_map = {"week": "Изменение за неделю",
                             "month": "Изменение за месяц",
                             "year":  "Изменение за год"}
                title = title_map.get(mode, "ZCYC Curve")

            self.ax.set_xlabel("Срок (лет)")
            self.ax.set_ylabel("Доходность (%)")
            self.ax.set_title(title)
            self.ax.grid(True, alpha=0.4)
            self.ax.legend()
            self.canvas.draw()

            self.info.configure(text=f"Загружено кривых: {len(curves)} — {list(curves.keys())}")

        except Exception as e:
            show_error("Ошибка загрузки ZCYC-кривой", e)


# =============================================================================
# 8. ГЛАВНОЕ ОКНО
# =============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Derivatives Pricing GUI")
        self.geometry("1000x780")

        # стиль
        try:
            style = ttk.Style(self)
            style.theme_use("clam")
        except tk.TclError:
            pass

        if _import_error is not None:
            # показываем ошибку сразу и даём возможность исправить
            messagebox.showerror("Ошибка импорта исходных модулей",
                str(_import_error) +
                f"\n\nBASE_DIR = {BASE_DIR}\n"
                f"Проверь, что файлы\n  {PRICING_FILE}\n  {ZCYC_FILE}\n  {CAP_FILE}\n"
                f"лежат рядом с pricing_gui.py, или поправь имена в шапке файла.")
            # Показываем минимальное окно и выходим, чтобы не падать дальше на AttributeError.
            ttk.Label(self, text="Не удалось импортировать исходные модули. Закрой окно.",
                      padding=20).pack()
            return

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        nb.add(OptionsTab(nb),   text="Options")
        nb.add(ForwardsTab(nb),  text="Forwards")
        nb.add(SwapTab(nb),      text="Swap IRS")
        nb.add(CapFloorTab(nb),  text="Cap / Floor")
        nb.add(ZCYCTab(nb),      text="ZCYC Curve")


if __name__ == "__main__":
    app = App()
    app.mainloop()
