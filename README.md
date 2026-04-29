# 📊 Quant Derivatives Pricing Platform

**Project for my coursework on "A platform with the function of analyzing and pricing derivatives and interest rate options"**

👉 *Скриншоты работы программы отображены ниже*

👉 *For English version scroll down*

---


## 🇷🇺 О проекте

Небольшая платформа для оценки деривативов. Дипломная работа с уклоном в quant.

Внутри реализованы основные типы инструментов:

* опционы (European / American)
* процентные деривативы (IRS, Cap/Floor)
* форварды и фьючерсы
* построение yield curve с MOEX API

Идея проекта — сделать **понятный и практичный pricing engine**, близкий к тому, как это делается в реальных задачах.

---
## 🎯 Примеры:
Модуль для вывода Zero Yield Curve, можно сравнивать 2 любые даты
<img width="998" height="654" alt="image" src="https://github.com/user-attachments/assets/ec0d6a2d-8dc4-4db2-bd56-460a3c8b6571" />

Модуль для оценки Фиксированной ноги IR SWAP
<img width="997" height="518" alt="image" src="https://github.com/user-attachments/assets/05cbec38-5edf-463f-b900-560029c47085" />

Модуль для оценки процентных опционов CAP/Floor
<img width="996" height="646" alt="image" src="https://github.com/user-attachments/assets/f053d383-42ac-477c-ab70-02240b854e9b" />


## ⚙️ Что внутри

* Black-Scholes, Black, Bachelier
* Monte Carlo, биномиальное дерево, LSM
* расчет греков (finite differences)
* работа с реальными данными (MOEX API)
* простой GUI на Tkinter

---

## 🚀 Запуск

```bash
pip install numpy pandas matplotlib seaborn scipy requests
python pricing_gui.py
```




---

# 🇬🇧 English

## 📊 About

A small derivatives pricing platform built as a coursework project with a quant focus.

Includes:

* options (European & American)
* interest rate products (IRS, Cap/Floor)
* forwards
* yield curve from MOEX

Goal: build a **simple but realistic pricing engine**.

---

## ⚙️ Features

* Black-Scholes, Black, Bachelier
* Monte Carlo, Binomial Tree, LSM
* Greeks (finite differences)
* MOEX market data
* Simple GUI

---

## 🚀 Run

```bash
pip install numpy pandas matplotlib seaborn scipy requests
python pricing_gui.py
```

---

## 🎯 What it shows

* derivatives knowledge
* pricing models implementation
* numerical methods
* working with real data

---
