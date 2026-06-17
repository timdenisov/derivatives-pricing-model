# Derivatives Pricing GUI

Дипломный проект — настольное приложение на Python для оценки производных финансовых инструментов и анализа рыночных данных.

Программа поддерживает:

* европейские и американские опционы;
* форварды, процентные свопы, cap и floor;
* расчёт Delta, Gamma, Vega, Theta и Rho;
* построение implied volatility surface;
* анализ опционных стратегий и Risk Matrix;
* загрузку кривых ставок MOEX и FRED;
* импорт данных из Excel и CSV.

В расчётах используются модели Black–Scholes, Bachelier, биномиальные и триномиальные деревья, метод Монте-Карло, численный поиск implied volatility и дисконтирование денежных потоков.

## Скриншоты

### Volatility Surface

![Volatility Surface](docs/images/vol_surface.png)

### Option Strategy

![Option Strategy](docs/images/option_strategy.png)

### ZCYC Curve

![ZCYC Curve](docs/images/zcyc_curve.png)

### 3D Implied Volatility Surface

![3D Implied Volatility Surface](docs/images/vol_surface_3d.png)

Проект предназначен для учебных и исследовательских целей.

## Основные модули

* `pricing_gui.py` — графический интерфейс приложения.
* `pricing__2_.py` — модели опционов, форвардов и IRS.
* `vol_surface.py` — implied volatility, Greeks и поверхность волатильности.
* `option_strategy.py` — оценка портфеля, P/L, Greeks и Risk Matrix.
* `rates_curves.py` — процентные кривые и discount factors.
* `market_chain.py` — импорт и подготовка рыночных котировок.
* `cap_floor_ruon.py` — оценка cap/floor на RUONIA.





# Derivatives Pricing GUI

Проект представляет собой desktop-приложение на Python/Tkinter для расчёта опционов, форвардов, свопов, cap/floor, процентных кривых, volatility surface и опционных стратегий.

## Запуск

1. Установить Python 3.10 или новее.
2. Поместить все файлы проекта в одну папку.
3. Установить зависимости:

```bash
pip install numpy pandas scipy requests seaborn matplotlib plotly kaleido mplcursors openpyxl
```

Для macOS/Linux при необходимости использовать:

```bash
python3 -m pip install numpy pandas scipy requests seaborn matplotlib plotly kaleido mplcursors openpyxl
```

4. Запустить приложение:

```bash
python pricing_gui.py
```

или:

```bash
python3 pricing_gui.py
```

Главное окно приложения откроется с вкладками для разных расчётов.

## Возможные проблемы

- Для загрузки рыночных и процентных данных нужен доступ к интернету.
- Если не открываются графики Plotly в PNG, проверьте установку `kaleido`.
- Если на Linux не запускается Tkinter, может потребоваться установка системного пакета `python3-tk`.
- Если возникают ошибки с зависимостями, повторно выполните команду установки библиотек.

По вопросам и проблемам писать на: tdenisov2004@gmail.com

## Описание файлов

- `pricing_gui.py` — главное GUI-приложение, объединяет все вкладки и вызывает расчётные модули.
- `pricing__2_.py` — базовые модели для опционов, форвардов и IRS-свопов.
- `vol_surface.py` — расчёт implied volatility, model price, Greeks и данных для volatility surface.
- `option_strategy.py` — расчёт опционных стратегий, payoff/profile, Greeks и risk matrix.
- `market_chain.py` — загрузка и нормализация market chain из CSV/Excel для Vol Surface и Option Strategy.
- `market_chain_template.xlsx` — шаблон Excel-файла для загрузки рыночной опционной цепочки.
- `rates_curves.py` — загрузка USD/CNY кривых ставок и расчёт discount/growth factors.
- `zcyc_построить_на_конкретный_день.py` — загрузка и построение MOEX ZCYC RUB-кривой.
- `cap_floor_ruon.py` — расчёт cap/floor на RUONIA по моделям Bachelier и Black.

## Результаты работы

При построении интерактивных графиков приложение создаёт файлы в папке `interactive_charts`. Эти файлы можно открывать в браузере или передавать отдельно.
