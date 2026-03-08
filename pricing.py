#! Установка библиотек через терминал: pip install numpy pandas matplotlib seaborn scipy 
#  pip install yfinance --upgrade

# на новых компах, где не был установлены библиотеки (для маков), используется pip3 install seaborn 

#ATM - at the money, OTM - out the money, ITM - in the money(Deep ITM - глубоко в деньгах)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt  
import seaborn as sns
import scipy as sc
# import yfinance as yf

from typing import List, Tuple, Optional

print("ok!")

#eurusd = yf.download( "EURUSD=X", period="1y", interval="1d")
 #print(eurusd.tail())

date_now = None #pd.Timestamp("2025-09-21") # можно оставить пустым, тогда подставиться сегодняшняя дата или подставить любую
date_executed = pd.Timestamp("2026-11-03")
 
if date_now is None:
    date_now = pd.Timestamp.today()  # сегодняшняя дата
else:
    date_now = pd.Timestamp(date_now)



#* можно вводить любое количество дат и выплат в эти даты. Если данные здесь есть, то обязательно q = 0!
div_dates = [pd.Timestamp("2025-11-29")] # вводить через запятую
div_amount = [0] # вводить через запятую

#! С див дохой разобраться, сейчас в формулах используется формула, что дивы платятся в самом начале, из-за этого будет неочень правильная цена акций с дивами(учтено в америк опционах)
#! Индексы считаются без дивов только, нужно исправить

derivative_type = "Option" # Реализован Option,Forward, Swap
S =  62.16 # текущая цена
K = 60 # страйк
T = (date_executed-date_now)/pd.Timedelta(days=365)# время до экспиры в годах
Rd = 0.0425 # Risk free ставка в валюте котирования
Rf = 0.025 #Risk free в базовой валюте foreign
Sig = 0.23809 #волатильность 
q = 0 #Див доходность(акции/индекса ) - годовая, если ее нет -  ставим "0" (Для американского опциона на equity реализована стратегия, что вычитаем дивы, которые придут во время срока жизни опциона)
option_type_country = "American" #European/American
Underl_Asset = "Index" # "Equity", "Index", "FX", "Commodity" 
Option_type = "Call" # Call/Put
N_sim = 5000 # кол-во симуляций и для биномиального дерева(не более 5000)
seed = 42 # Для одинаковой симуляции каждый раз( используется в numpy)
N_steps = 100 # СКолько периодов в году( например: 12 - движение разбивается помесячно, 52 - по недельно, 252 - по дням). Используется в MC и регрессией( Equity US opt)
Poly_degree= 3 # степень полинома для регрессии. Используется в MC и регрессией( Equity US opt)


#* Используется только для commodity Forwards
cost_of_carry = 0.0 # Используется только для commodity Forwards в формуле это u
storage_payments = [] # формат ["2025-09-12", 2] - сначала дата, потом идет стоимость за хранение

y = 0.0 # convince yield, прибыль в годовых если продать прямо сейчас?

# Пример заполнения storage_payments
# storage_payments = [
#    (pd.Timestamp("2025-10-20"), 0.5),
#    (pd.Timestamp("2026-01-01"), 0.3)
# ] """

    






#! EUR Options

#* spot Equities


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

        # d1
        self.d1 = (np.log(self.S/self.K)+(self.Rd -self.q+self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))
        # d2
        self.d2 = (np.log(self.S/self.K)+(self.Rd-self.q-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)
        # -Nd1
        self.Nd1m = sc.stats.norm.cdf(-self.d1)

        # Nd2
        self.Nd2 = sc.stats.norm.cdf(self.d2)
        # -Nd2
        self.Nd2m = sc.stats.norm.cdf(-self.d2)

        #  Call price
    def Call_price(self):
        return self.S*np.exp(-self.q*self.T)*self.Nd1 - self.K*np.exp(-self.Rd*self.T)*self.Nd2
        #  Put price
    def Put_price(self):
        return self.K*np.exp(-self.Rd*self.T)*self.Nd2m-self.S*np.exp(-self.q*self.T)*self.Nd1m

    def Monte_carlo_sim(self): 
        
        # Генерация случайных траекторий EQ
        S_T = self.S*np.exp((self.Rd -self.q- 0.5*self.Sig**2)*self.T+self.Sig*np.sqrt(self.T)*np.random.randn(self.N_sim))

        #расчет payoff
        if self.Option_type.lower() == "call":
            payoffs =np.maximum(S_T-self.K,0) #симуляция n_sim раз для call
        else:
            payoffs = np.maximum(self.K-S_T,0) #симуляция n_sim раз для call для put

        #Дисконтирование
        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price

#* spot Indexes
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

        # d1
        self.d1 = (np.log(self.S/self.K)+(self.Rd-self.q+self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))
        # d2
        self.d2 = (np.log(self.S/self.K)+(self.Rd-self.q-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)
        # -Nd1
        self.Nd1m = sc.stats.norm.cdf(-self.d1)

        # Nd2
        self.Nd2 = sc.stats.norm.cdf(self.d2)
        # -Nd2
        self.Nd2m = sc.stats.norm.cdf(-self.d2)

        #  Call price
    def Call_price(self):
        return self.S*np.exp(self.q*self.T)*self.Nd1 - self.K*np.exp(-self.Rd*self.T)*self.Nd2
        #  Put price
    def Put_price(self):
        return self.K*np.exp(-self.Rd*self.T)*self.Nd2m-self.S*np.exp(self.q*self.T)*self.Nd1m

    def Monte_carlo_sim(self): 
        
        # Генерация случайных траекторий EQ
        S_T = self.S*np.exp((self.Rd - self.q - 0.5*self.Sig**2)*self.T+self.Sig*np.sqrt(self.T)*np.random.randn(self.N_sim))

        #расчет payoff
        if self.Option_type.lower() == "call":
            payoffs =np.maximum(S_T-self.K,0) #симуляция n_sim раз для call
        else:
            payoffs = np.maximum(self.K-S_T,0)#симуляция n_sim раз для call для put

        #Дисконтирование
        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price

#* Futures FX
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
        # d1
        self.d1 = (np.log(self.S/self.K)+(self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))
        # d2
        self.d2 = (np.log(self.S/self.K)+(-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)
        # -Nd1
        self.Nd1m = sc.stats.norm.cdf(-self.d1)

        # Nd2
        self.Nd2 = sc.stats.norm.cdf(self.d2)
        # -Nd2
        self.Nd2m = sc.stats.norm.cdf(-self.d2)

        #  Call price
    def Call_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd1-self.K*self.Nd2)
        #  Put price
    def Put_price(self):
        return np.exp(-self.Rd*self.T)*(self.K*self.Nd2m-self.S*self.Nd1m)

    def Monte_carlo_sim(self): 
        
        # Генерация случайных траекторий EQ
        

        F_T = self.S*np.exp((-0.5*self.Sig**2)*self.T+self.Sig*np.sqrt(self.T)*np.random.randn(self.N_sim))

        #расчет payoff
        if self.Option_type.lower() == "call":
            payoffs =np.maximum(F_T-self.K,0) #симуляция n_sim раз для call
        else:
            payoffs = np.maximum(self.K-F_T,0)#симуляция n_sim раз для call для put

        #Дисконтирование
        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price


#* Futures Commodities
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
        # d1
        self.d1 = (np.log(self.S/self.K)+(self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))
        # d2
        self.d2 = (np.log(self.S/self.K)+(-self.Sig**2/2)*self.T)/(self.Sig*(self.T**0.5))

        self.Nd1 = sc.stats.norm.cdf(self.d1)
        # -Nd1
        self.Nd1m = sc.stats.norm.cdf(-self.d1)

        # Nd2
        self.Nd2 = sc.stats.norm.cdf(self.d2)
        # -Nd2
        self.Nd2m = sc.stats.norm.cdf(-self.d2)

        #  Call price
    def Call_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd1-self.K*self.Nd2)
        #  Put price
    def Put_price(self):
        return np.exp(-self.Rd*self.T)*(self.S*self.Nd2m-self.S*self.Nd1m)

    def Monte_carlo_sim(self): 
        
        # Генерация случайных траекторий EQ
        

        F_T = self.S*np.exp((-0.5*self.Sig**2)*self.T+self.Sig*np.sqrt(self.T)*np.random.randn(self.N_sim))

        #расчет payoff
        if self.Option_type.lower() == "call":
            payoffs =np.maximum(F_T-self.K,0) #симуляция n_sim раз для call
        else:
            payoffs = np.maximum(self.K-F_T,0)#симуляция n_sim раз для call для put

        #Дисконтирование
        price = np.exp(-self.Rd*self.T)*np.mean(payoffs)
        return price



#! US Options

class US_S_EQ_option:
    def __init__(self, S, K, T, Rd, Sig, q, Option_type, N_sim,N_steps, Poly_degree, div_dates = None, div_amounts = None, date_now = None, seed= None):
        self.S = S
        self.K = K
        self.T = T
        self.Rd = Rd
        self.Sig=Sig
        self.Q= q
        self.Option_type = Option_type
        self.seed = seed
        self.N_sim=N_sim
        self.N_steps = N_steps  
        self.Poly_degree = Poly_degree
        self.seed = seed

        # Предвычесленные параметры для бин модели

        self.Step = self.T / self.N_steps

        self.Disc = np.exp(-self.Rd*self.Step)
        self.U = np.exp(self.Sig*np.sqrt(self.Step))
        self.D = 1/self.U
        self.P = (np.exp((self.Rd-self.Q)*self.Step) - self.D)/(self.U-self.D)

        # данные для точного диск дивидендов

        self.div_date = div_dates if div_dates is not None else []
        self.div_amount = div_amounts if div_amounts is not None else []

        self.date_now = date_now

        self.adjust_price_for_div()

    
    def adjust_price_for_div(self):
        if self.div_date is not None and self.div_amount is not None and self.date_now is not None:
            for div_date, div_amount in zip(self.div_date, self.div_amount):
                if self.date_now<= div_date<= self.date_now+pd.Timedelta(days=int(self.T*365)):
                    t_div= (div_date - self.date_now)/pd.Timedelta(days= 365)
                    pv_div = div_amount*np.exp(-self.Rd*t_div)
                    self.S -= pv_div

    def price(self):

        J = np.arange(self.N_sim, -1, -1)

        ST = self.S*(self.U**(self.N_sim -J))*(self.D ** J)

        if self.Option_type == "Call":
            values = np.maximum(ST-self.K,0.0)
        else:
            values = np.maximum(self.K-ST,0.0)

        for i in range(self.N_sim-1, -1, -1):
            #asset price at time i
            J = np.arange(i, -1, -1)
            Si = self.S*(self.U**(i - J))*(self.D ** J)
        
            Continuation = self.Disc * (self.P * values[0:i+1] + (1 - self.P) * values[1:i+2])

            if self.Option_type == "Call":
                Exercise = np.maximum(Si-self.K,0.0)
            else:
                Exercise = np.maximum(self.K-Si,0.0)
        
            values = np.maximum(Exercise, Continuation)

        return float(values[0])
    
    def generate_paths(self):
        np.random.seed(self.seed)
        dt = self.T / self.N_steps
        S_paths= np.zeros((self.N_sim,self.N_steps+1))
        S_paths[:,0] = self.S

        div_steps = []
        div_values = []

        if self.date_now is not None:
            for d_date, d_amount in zip(self.div_date, self.div_amount):
                    t_div = (d_date - self.date_now)/pd.Timedelta(days=365)
                    step = int(t_div*self.N_steps)
                    div_steps.append(step)
                    div_values.append(d_amount)


        for t in range(1,self.N_steps+1):
            Z = np.random.randn(self.N_sim)
            S_paths[:,t] = S_paths[:,t-1]*np.exp((self.Rd -self.Q - 0.5*self.Sig**2)*dt+self.Sig*np.sqrt(dt)*Z)
            
            if t in div_steps:
                idx = div_steps.index(t)
                S_paths[:,t] -= div_values[idx]*np.exp(-self.Rd*(self.T-t*dt))
                            
        return S_paths


    def payoff(self,S):
        if self.Option_type == "Call":
            return np.maximum(S-self.K,0)
        else:
            return np.maximum(self.K-S,0)

    def Monte_carlo_sim(self):
        S_paths = self.generate_paths()
        dt=self.T/self.N_steps
        V=self.payoff(S_paths[:,-1])

        for t in range(self.N_steps-1,0,-1):
            St=S_paths[:,t]
            epsilon  = 0.01*self.K
            itm = self.payoff(St)> -epsilon #включает еще несколько вариаций дополнительных, где опцион OTM но очень рядом с ATM

            X = St[itm]
            Y = V[itm] * np.exp(-self.Rd * dt)

            # 🔒 Защита от пустого ITM множества
            if len(X) < self.Poly_degree + 1:
                continuation = np.zeros_like(St)
            else:
                coeffs = np.polyfit(X, Y, self.Poly_degree)
                continuation = np.polyval(coeffs, St)


        return np.mean(V)
    
    

#! Для греков на опционы, все

def calc_greeks(
    option_class,
    S, K, T, Rd, Sig,
    q=0.0,
    Option_type="Call",
    N_sim=10000,
    seed=42,
    # только для US опционов
    N_steps=None,
    Poly_degree=None,
    div_dates=None,
    div_amounts=None,
    date_now=None,
    # шаги конечных разностей
    h=0.01,
    dt=1/365,
    dr=0.0001
):
    """
    Универсальный численный расчёт греков (bump-and-reprice).
    Работает с:
    - Европейскими опционами (аналитика / MC)
    - Американскими опционами (биномиалка / LSM)
    """

    # -------------------------------------------------
    # Функция создания опциона (фабрика)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Унифицированный вызов цены
    # -------------------------------------------------
    def get_price(opt):
        if hasattr(opt, "Call_price") or hasattr(opt, "Put_price"):
            return opt.Call_price() if Option_type == "Call" else opt.Put_price()
        elif hasattr(opt, "price"):
            return opt.price()
        elif hasattr(opt, "Monte_carlo_sim"):
            return opt.Monte_carlo_sim()
        else:
            raise ValueError("Объект не имеет метода расчёта цены.")

    # -------------------------------------------------
    # Базовая цена
    # -------------------------------------------------
    opt = make_opt()
    price = get_price(opt)

    # -------------------------------------------------
    # Delta / Gamma
    # -------------------------------------------------
    opt_up = make_opt(S_=S + h)
    opt_down = make_opt(S_=S - h)

    price_up = get_price(opt_up)
    price_down = get_price(opt_down)

    delta = (price_up - price_down) / (2 * h)
    gamma = (price_up - 2 * price + price_down) / (h ** 2)

    # -------------------------------------------------
    # Vega
    # -------------------------------------------------
    opt_vega = make_opt(Sig_=Sig + h)
    price_vega = get_price(opt_vega)
    vega = (price_vega - price) / h

    # -------------------------------------------------
    # Theta
    # -------------------------------------------------
    if T > dt:
        opt_theta = make_opt(T_=T - dt)
        price_theta = get_price(opt_theta)
        theta = (price_theta - price) / dt
    else:
        theta = float("nan")

    # -------------------------------------------------
    # Rho
    # -------------------------------------------------
    opt_rho = make_opt(Rd_=Rd + dr)
    price_rho = get_price(opt_rho)
    rho = (price_rho - price) / dr

    # -------------------------------------------------
    # Результат
    # -------------------------------------------------
    return {
        "Price": price,
        "Delta": delta,
        "Gamma": gamma,
        "Vega": vega,
        "Theta": theta,
        "Rho": rho
    }



#! Forward

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
        u, #непрерывный storage cost
        y, # convince yield
        date_now,
        storage_payments: Optional[List[Tuple[pd.Timestamp, float]]] = None # дискретные платежи
        ):
        self.S = S
        self.T = T
        self.Rd = Rd
        self.u= cost_of_carry
        self.y = y
        self.storage_payments =storage_payments if storage_payments else []
        self.date_now = date_now  
    def forward_price(self):
        # Базовый вклад cost-of-carry (continuous)
        F_cont = self.S*np.exp((self.Rd+self.u-self.y)*self.T)

        #return self.S*np.exp((self.Rd+self.cost_of_carry)*self.T) #простая формула для расчетного

        # Добавляем дискретные storage payments
        extra = 0.0
        for pay_date, amount in self.storage_payments:
            pay_date = pd.Timestamp(pay_date)
            if self.date_now <= pay_date <= self.date_now + pd.Timedelta(days = int(self.T*365+1)):
                t_j = (pay_date -self.date_now)/ pd.Timedelta(days=365)
                extra += amount * np.exp(self.Rd*(self.T -t_j))

        return F_cont+extra






#? Определение какой класс будет выполняться
if derivative_type == "Option":
    if option_type_country == "European":
        if Underl_Asset == "Equity" or Underl_Asset == "Index":
            option_price = EUR_S_EQ_option(
                S=S,
                K=K,
                T=T,
                Rd=Rd,
                Sig=Sig,
                q = q, 
                Option_type = Option_type,
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
                q = q,
                Option_type = Option_type,
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
                q = q,
                Option_type = Option_type,
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
                q = q,
                Option_type = Option_type,
                N_sim=N_sim,
                div_dates = div_dates,
                div_amounts = div_amount,
                date_now = date_now,
                seed= seed,
                N_steps = N_steps, 
                Poly_degree = Poly_degree
                )
if derivative_type == "Forward":
    if Underl_Asset == "FX":
        forward_price = S_FX_fwd(
                S=S,
                T=T,
                Rd=Rd,
                Rf=Rf
                )
                
    if Underl_Asset  in ("Index", "Equity"):
        forward_price = S_FX_fwd(
                S=S,
                T=T,
                Rd=Rd,
                Rf=Rf
                )
    if Underl_Asset == "Commodity":  
        if Underl_Asset == "Commodity":
            forward_price = S_Commodity_fwd(
                S=S,
                T=T,
                Rd=Rd,
                u=cost_of_carry,        # continuous storage cost
                y=y,                     # convenience yield
                storage_payments=storage_payments,  # список дискретных платежей
                date_now=date_now
                ) 



#? Вывод ответов




if derivative_type == "Option":
    if option_type_country == "European":
        print(f"Option ({Underl_Asset}, European, {Option_type}) price:")
        analytical_price = option_price.Call_price() if Option_type == "Call" else option_price.Put_price()
        print(f"Analytical: {analytical_price:.4f}")
        price_mc = option_price.Monte_carlo_sim()
        print(f"Monte Carlo: {price_mc:.4f}")

        # 🔹 Расчёт греков
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

        # 🔹 Расчёт греков для американских опционов
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