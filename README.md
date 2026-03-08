# derivatives-pricing-model
Project for my coursework on "A platform with the function of analyzing trading strategies using vanilla and interest rate options"

Derivatives Pricing System
🇬🇧 English Version
Project Description

This repository contains the source code of a system for pricing derivative financial instruments. The project was developed as part of a research work focused on quantitative methods for derivative pricing.
The system implements several modules for:
option pricing
forward contract valuation
interest rate derivatives pricing
volatility estimation based on historical market data

The project is implemented in Python using the following libraries:
NumPy
Pandas
SciPy
Matplotlib

Repository Structure
pricing.py

The pricing.py module contains implementations of pricing models for several types of derivative instruments.
Implemented instruments include:
European options (vanilla options)
American options
forward contracts
interest rate swaps
basic derivative instruments

Pricing methods include:
analytical models
binomial tree models
Monte Carlo simulation
This module represents the core pricing engine of the system.

Volatility.py
The Volatility.py module estimates volatility based on historical price data.
Implemented volatility measures include:
historical volatility
log-return volatility
rolling volatility

The module allows users to:
load market data
compute volatility
visualize price dynamics
generate candlestick charts

Market Data Source
Historical data is recommended to be downloaded from FINAM:
https://www.finam.ru/profile/moex-akcii/gazprom/export/

Expected data format:
TICKER;PER;DATE;TIME;OPEN;HIGH;LOW;CLOSE;VOL
This format ensures compatibility with the volatility module.

valuation options on key rate.py
This module implements valuation models for interest rate derivatives, including:
Interest Rate Caps
Interest Rate Floors
options on interest rates
Pricing is performed using the Vasicek interest rate model.
The model simulates short-term interest rate dynamics and prices options using Monte Carlo simulation.

Data Sources
Cbonds
Historical interest rate data can be obtained from Cbonds:
https://cbonds.ru/

These data can be used for:
calibrating Vasicek model parameters
constructing historical interest rate series
evaluating interest rate derivatives

Alternatively, model parameters can be estimated independently and specified directly in the code.

🇷🇺 Русская версия
Описание проекта

Данный репозиторий содержит программный код системы для оценки производных финансовых инструментов (ПФИ). Проект разработан в рамках исследовательской работы и предназначен для анализа и оценки стоимости различных типов деривативов с использованием аналитических и численных методов.

Система включает несколько модулей, реализующих:
оценку опционов
расчет форвардных контрактов
оценку процентных деривативов
расчет волатильности на основе исторических рыночных данных
Код написан на языке Python с использованием библиотек:

NumPy
Pandas
SciPy
Matplotlib

Структура репозитория
pricing.py

Модуль pricing.py содержит реализацию моделей оценки основных типов производных финансовых инструментов.
Реализованные инструменты:
европейские опционы (vanilla options)
американские опционы
форвардные контракты
процентные свопы
другие базовые производные финансовые инструменты

В модуле используются различные методы оценки:
аналитические формулы
биномиальные модели
метод Монте-Карло
Данный модуль является основным компонентом системы оценки ПФИ.

Volatility.py
Модуль Volatility.py предназначен для расчета волатильности на основе исторических данных котировок.
Реализованы следующие методы расчета:
историческая волатильность
волатильность на основе логарифмических доходностей
скользящая (rolling) волатильность

Программа позволяет:
загружать данные котировок
рассчитывать волатильность
визуализировать данные
строить свечные графики
Источник данных

Для корректной работы рекомендуется использовать исторические данные котировок, загруженные с сайта FINAM.

Источник данных:
https://www.finam.ru/profile/moex-akcii/gazprom/export/

Файлы должны быть приведены к следующему формату:
TICKER;PER;DATE;TIME;OPEN;HIGH;LOW;CLOSE;VOL
Этот формат используется платформой FINAM и обеспечивает корректную обработку временных рядов.

valuation options on key rate.py
Данный модуль предназначен для оценки процентных деривативов:

Interest Rate Cap
Interest Rate Floor
опционы на процентные ставки
Оценка осуществляется на основе модели Васичека (Vasicek interest rate model).

Модель используется для моделирования динамики краткосрочной процентной ставки и последующей оценки стоимости процентных опционов методом Monte Carlo simulation.

Источники данных
Cbonds
Для работы с процентными инструментами и получения исторических данных по процентным ставкам рекомендуется использовать платформу Cbonds:
https://cbonds.ru/

Эти данные могут использоваться для:
калибровки параметров модели Vasicek
построения временных рядов процентных ставок
оценки процентных деривативов
При необходимости параметры модели (волатильность, средняя ставка, скорость возврата к среднему) могут быть рассчитаны самостоятельно и заданы непосредственно в коде.

Назначение проекта

Данный программный комплекс предназначен для:
количественного анализа производных финансовых инструментов
тестирования моделей ценообразования
анализа чувствительности (Greeks)
исследовательских и учебных задач в области количественных финансов




