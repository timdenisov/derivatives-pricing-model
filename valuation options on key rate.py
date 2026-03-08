import numpy as np
import pandas as pd

# Параметры модели Vasicek
r0 = 0.1685        # начальная ставка RUONIA%  - текущую ключевую/межбанковскую ставку в момент t0 
a = 0.40009424        # скорость возврата к среднему
b = 0.171738408      # средняя ставка
sigma = 0.023328   # волатильность hist vol
T = 0.101369863         # срок опциона, годы
N = 365          # количество шагов по времени (дни)
dt = T / N
K = 0.169       # страйк (целевая ставка)
n_paths = 10000 # количество симуляций Monte Carlo

# Можно расчитать данные для заданных дат

# Опциональные параметры
start_date_str = "2025-09-17"  #  можно вписать "2025-10-01" или оставить пустым
end_date_str = "2025-10-24"    # тоже самое для конца

# Конвертируем в pd.Timestamp, если строки не пустые
start_date = pd.Timestamp(start_date_str) if start_date_str else None
end_date = pd.Timestamp(end_date_str) if end_date_str else None
"""
# Загружаем данные
df = pd.read_excel("ключевая-ставка-цб-рф-на-каждый-рабочий-день (2).xlsx")


df1 = df

# Фильтруем только если даты заданы
if start_date is not None:
    df = df[df["Дата"] >= start_date]
if end_date is not None:
    df = df[df["Дата"] <= end_date]

### внести расчеты для предыдущих дат вставить условие, чтобы часть таблиы удаляется, ок - только те которые удовлетворяют условиям



df1["t+1"] = df1["Ключевая ставка ЦБ РФ на каждый рабочий день"].shift(-1)
df1["delta"] = df1["t+1"] - df1["Ключевая ставка ЦБ РФ на каждый рабочий день"]

df1["vol"] = np.log(df1["Ключевая ставка ЦБ РФ на каждый рабочий день"]/df1["Ключевая ставка ЦБ РФ на каждый рабочий день"].shift(1))


avg_key_rate = df1["Ключевая ставка ЦБ РФ на каждый рабочий день"].mean()

avg_delta = df1["delta"].mean()

df1["числ"] = (df1["Ключевая ставка ЦБ РФ на каждый рабочий день"] - avg_key_rate)*( df1["delta"] - avg_delta)

df1["знам"] = (df1["Ключевая ставка ЦБ РФ на каждый рабочий день"] - avg_key_rate) ** 2

chislitel = df1["числ"].sum()

znam = df1["знам"].sum()

hist_vol = df1["vol"].std()

print(hist_vol)

b1 = chislitel/znam

b0 = avg_key_rate-b1*avg_delta

a = -b1/N 

b = b0/(a*N)

print(df1.head())
# Используем параметры найденные в эксельке
"""




# Функция генерации траекторий ставки
def simulate_vasicek_paths(r0, a, b, sigma, T, N, n_paths):
    dt = T / N
    r = np.zeros((n_paths, N + 1))
    r[:,0] = r0
    for t in range(1, N + 1):
        dr = a * (b - r[:, t-1]) * dt + sigma * np.sqrt(dt) * np.random.randn(n_paths)
        r[:, t] = r[:, t-1] + dr
    return r

# Генерация траекторий
rates = simulate_vasicek_paths(r0, a, b, sigma, T, N, n_paths)


payoffs = np.maximum(rates[:,1:] - K , 0)  # если call опцион
discount_factors = np.exp(-np.cumsum(rates[:, :-1]*dt, axis=1))
discounted_payoffs = payoffs * discount_factors
option_values = np.max(discounted_payoffs, axis=1)  # американское исполнение

# avg cost option
option_price = np.mean(option_values)
print(f"Цена американского опциона на ключевую ставку: {option_price:.6f}")

