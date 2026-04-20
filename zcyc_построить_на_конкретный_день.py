import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta



"""

код для запуска 



loader = ZCYCCurveLoader()
loader.show(mode="custom", from_date="2026-03-10", to_date="2026-04-16")



"""

class ZCYCCurveLoader:
    def __init__(self):
        self.base_url = "https://iss.moex.com/iss/engines/stock/zcyc/yearyields.json"

    def _fetch_curve(self, date_str):
        params = {"date": date_str}
        r = requests.get(self.base_url, params=params, timeout=30)
        data = r.json()

        if "yearyields" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(
            data["yearyields"]["data"],
            columns=data["yearyields"]["columns"]
        )

        if df.empty:
            return pd.DataFrame()

        df = df[["tradedate", "tradetime", "period", "value"]].copy()
        df["period"] = pd.to_numeric(df["period"])
        df["value"] = pd.to_numeric(df["value"])
        return df

    def get_curve(self, date_str, max_lookback_days=7, verbose=True):
        """
        Загружает кривую на date_str.
        Если данных нет, откатывается назад до max_lookback_days.
        """
        base_date = datetime.strptime(date_str, "%Y-%m-%d")

        for i in range(max_lookback_days + 1):
            test_date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
            df = self._fetch_curve(test_date)

            if not df.empty:
                if verbose:
                    print(f"Используется дата: {test_date}")
                return df

        raise ValueError(f"Не удалось найти данные за дату {date_str} и предыдущие {max_lookback_days} дней")

    def get_curves_for_dates(self, dates, max_lookback_days=7, verbose=True):
        """
        Загружает несколько кривых по списку дат.
        Возвращает словарь: {фактическая_дата: dataframe}
        """
        result = {}

        for date_str in dates:
            df = self.get_curve(date_str, max_lookback_days=max_lookback_days, verbose=verbose)
            actual_date = str(df["tradedate"].iloc[0])
            result[actual_date] = df

        return result

    def get_predefined_dates(self, base_date_str, mode):
        """
        mode:
        - 'single' : только base_date
        - 'week'   : base_date и дата неделей раньше
        - 'month'  : base_date и дата месяц назад (30 дней)
        - 'year'   : base_date и дата год назад (365 дней)
        """
        base_date = datetime.strptime(base_date_str, "%Y-%m-%d")

        if mode == "single":
            return [base_date.strftime("%Y-%m-%d")]
        elif mode == "week":
            return [
                (base_date - timedelta(days=7)).strftime("%Y-%m-%d"),
                base_date.strftime("%Y-%m-%d")
            ]
        elif mode == "month":
            return [
                (base_date - timedelta(days=30)).strftime("%Y-%m-%d"),
                base_date.strftime("%Y-%m-%d")
            ]
        elif mode == "year":
            return [
                (base_date - timedelta(days=365)).strftime("%Y-%m-%d"),
                base_date.strftime("%Y-%m-%d")
            ]
        else:
            raise ValueError("mode должен быть: 'single', 'week', 'month' или 'year'")

    def get_custom_dates(self, from_date, to_date):
        return [from_date, to_date]

    def plot_curves(self, curves_dict, title="ZCYC Curve"):
        plt.figure(figsize=(10, 6))

        for curve_date, df in curves_dict.items():
            df = df.sort_values("period")
            plt.plot(df["period"], df["value"], marker="o", label=curve_date)

        plt.xlabel("Срок (лет)")
        plt.ylabel("Доходность (%)")
        plt.title(title)
        plt.grid(True)
        plt.legend()
        plt.show()

    def show(self, base_date=None, mode="single", from_date=None, to_date=None, max_lookback_days=7):
        """
        Основной метод для пользователя.

        Варианты:
        1) Одна дата:
           show(base_date="2026-04-16", mode="single")

        2) Сравнение за неделю/месяц/год:
           show(base_date="2026-04-16", mode="week")
           show(base_date="2026-04-16", mode="month")
           show(base_date="2026-04-16", mode="year")

        3) Кастомные даты:
           show(mode="custom", from_date="2026-03-01", to_date="2026-04-16")
        """
        if mode == "custom":
            if not from_date or not to_date:
                raise ValueError("Для mode='custom' нужно задать from_date и to_date")
            dates = self.get_custom_dates(from_date, to_date)
            curves = self.get_curves_for_dates(dates, max_lookback_days=max_lookback_days)
            self.plot_curves(curves, title=f"Сравнение кривых: {from_date} vs {to_date}")
        else:
            if not base_date:
                raise ValueError("Нужно задать base_date")
            dates = self.get_predefined_dates(base_date, mode)
            curves = self.get_curves_for_dates(dates, max_lookback_days=max_lookback_days)

            if mode == "single":
                title = f"Кривая бескупонной доходности на дату {list(curves.keys())[0]}"
            elif mode == "week":
                title = "Изменение кривой за неделю"
            elif mode == "month":
                title = "Изменение кривой за месяц"
            elif mode == "year":
                title = "Изменение кривой за год"
            else:
                title = "ZCYC Curve"

            self.plot_curves(curves, title=title)