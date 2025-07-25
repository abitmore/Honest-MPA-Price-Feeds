"""
+===============================+
  ╦ ╦  ╔═╗  ╔╗╔  ╔═╗  ╔═╗  ╔╦╗
  ╠═╣  ║ ║  ║║║  ║╣   ╚═╗   ║
  ╩ ╩  ╚═╝  ╝╚╝  ╚═╝  ╚═╝   ╩
    MARKET - PEGGED - ASSETS
+===============================+

live forex rates scraped from 14 sources:

liveusd, freeforex, finviz, yahoo, wsj, duckduckgo(xe), wocu, oanda, reuters(refinitiv)
fxrate, forextime, currencyme, forexrates, exchangeratewidget


litepresence2020
"""

import sys

# STANDARD PYTHON MODULES
import time
from json import dumps as json_dumps
from json import loads as json_loads

# THIRD PARTY MODULES
import requests

# PRICE FEED MODULES
from utilities import it, race_write, refine_data


def liveusd(site):
    """
    live forex rates scraped from liveusd.com
    """
    url = "http://liveusd.com/veri/refresh/total.php"
    try:
        ret = requests.get(url, timeout=(15, 15)).text
        ret = ret.replace(" ", "").split("\n")
        data = {}
        for item in ret:
            if item:
                try:
                    pair = item.split(":")[0].replace("USD", "USD:")
                    price = item.split(":")[1]
                    data[pair] = float(price)
                except:
                    pass
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def yahoo(site):
    """
    live forex rates scraped from yahoo finance
    XAU and XAG are stale
    CG=F is a gold 30 day future
    SI=F is silver 60 day future
    """
    uri = "https://query1.finance.yahoo.com/v7/finance/spark?symbols=USD"
    try:
        currencies = ["EUR", "CNY", "RUB", "KRW", "JPY"]
        data = {}
        for currency in currencies:
            endpoint = f"{currency}%3DX&range=1m&interval=1m"
            url = uri + endpoint
            raw = requests.get(url, timeout=(15, 15)).json()
            ret = raw["spark"]["result"][0]["response"][0]["meta"]["regularMarketPrice"]
            data["USD:" + currency] = float(ret)
            time.sleep(1)
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def duckduckgo(site):
    """
    live forex rates scraped from XE via duckduckgo.com
    """
    uri = "https://duckduckgo.com/js/spice/currency/1/usd/"
    try:
        data = {}
        currencies = ["CNY", "XAU", "XAG", "RUB", "EUR", "GBP", "JPY", "KRW"]
        for currency in currencies:
            if currency in ["XAU", "XAG"]:
                url = uri.replace("usd/", "") + currency + "/usd"
            else:
                url = uri + currency
            raw = requests.get(url, timeout=(15, 15)).text
            raw = (
                raw.replace("\n", "")
                .replace(" ", "")
                .replace("ddg_spice_currency(", "")
                .replace(");", "")
            )
            ret = json_loads(raw)
            if currency in ["XAU", "XAG"]:
                data["USD:" + currency] = (
                    1 / [i["mid"] for i in ret["to"] if i["quotecurrency"] == "USD"][0]
                )
            else:
                data["USD:" + currency] = [
                    i["mid"] for i in ret["to"] if i["quotecurrency"] == currency
                ][0]
            time.sleep(1)
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def wocu(site):
    """
    live forex rates scraped from wocu.com
    XAU XAG are not precise
    """

    def parse(raw, symbol):
        """
        attempt to extract a float value from the html matrix
        """
        return float(raw.split(symbol)[1].split("</td>")[2].split(">")[1])

    url = "http://54.154.247.217/wocutab.php"
    symbols = ["EUR", "RUB", "GBP", "KRW", "CNY", "JPY"]
    try:
        raw = requests.get(url, timeout=(15, 15)).text
        data = {}
        for symbol in symbols:
            try:
                data["USD:" + symbol] = parse(raw, symbol)
            except:
                pass
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def oanda(site):
    """
    make external request, decode, decrypt, reformat to dict
    """
    key = "aaf6cb4f0ced8a211c2728328597268509ade33040233a11af"
    url = "https://www1.oanda.com/lfr/rates_lrrr?tstamp="

    def hex_decode(raw):
        """
        latin-1 from hexidecimal
        """
        return bytes.fromhex("0" + raw if len(raw) % 2 else raw).decode("latin-1")

    def rc4(cypher, key):
        """
        decryption of rc4 stream cypher from latin-1
        """
        idx1 = 0
        output = []
        r256 = [*range(256)]
        for idx2 in range(256):
            idx1 = (idx1 + r256[idx2] + ord(cypher[idx2 % len(cypher)])) % 256
            r256[idx2], r256[idx1] = r256[idx1], r256[idx2]
        idx1, idx2 = 0, 0
        for _, item in enumerate(key):
            idx2 = (idx2 + 1) % 256
            idx1 = (idx1 + r256[idx2]) % 256
            r256[idx2], r256[idx1] = r256[idx1], r256[idx2]
            output.append(chr(ord(item) ^ r256[(r256[idx2] + r256[idx1]) % 256]))
        return ("").join(output)

    try:
        while True:
            try:
                millies = str(int(round(time.time() * 1000)))
                raw = requests.get(url + millies, timeout=(15, 15)).text
                hex_decoded = hex_decode(raw)
                decrypted = rc4(key, hex_decoded)
                break
            except:
                time.sleep(5)
        content = decrypted.split("\n")
        parsed = {
            raw.split("=")[0]: (float(raw.split("=")[1]) + float(raw.split("=")[2])) / 2
            for raw in content
        }
        data = {}
        for pair, price in parsed.items():
            data[pair.replace("/", ":")] = float(price)
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def currencyme(site):
    """
    live forex rates scraped from currency.me.uk
    """
    symbols = ["EUR", "RUB", "GBP", "KRW", "CNY", "JPY"]
    url = "https://www.currency.me.uk/remote/ER-CCCS2-AJAX.php"
    try:
        data = {}
        for symbol in symbols:
            try:
                params = {"ConvertTo": symbol, "ConvertFrom": "USD", "amount": 1}
                raw = requests.get(url, params=params, timeout=(15, 15)).text
                data["USD:" + symbol] = float(raw.replace(" ", ""))
            except:
                pass
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def ratewidget(site):
    """
    live forex rates scraped from exchangeratewidget.com
    """
    url = "https://www.exchangeratewidget.com/converter.php?v=11&t="
    symbols = ["USDEUR", "USDGBP", "USDJPY", "USDCNY", "USDRUB", "USDKRW"]
    for symbol in symbols:
        url += symbol + ","
    try:
        data = {}
        raw = requests.get(url, timeout=20).text
        for symbol in symbols:
            currency = symbol.replace("USD", "")
            price = raw.split(currency)[1].split("</span>")[1].split(">")[1]
            data["USD:" + currency] = float(price)
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def forexrates(site):
    """
    live forex rates scraped from forexrates.net
    """

    def parse(raw):
        """
        remove xml tags, return list of rates split with =
        """
        lines = [i.split(";")[0] for i in raw.split("Values")]
        lines.pop(0)
        return [
            i.replace('"', "").replace("[", "").replace("]", "").replace(" ", "")
            for i in lines
        ]

    url = "https://www.forexrates.net/widget/FR-FRW-2.php?"
    symbols = "c1=USD/EUR&c2=USD/GBP&c3=USD/RUB&c4=USD/JPY&c5=USD/CNY"
    url += symbols
    try:
        raw = requests.get(url, timeout=20).text
        rates = parse(raw)
        data = {}
        for rate in rates:
            symbol = rate.split("=")[0].replace("USD", "USD:")
            price = float(rate.split("=")[1])
            data[symbol] = price
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def aastock(site):
    """
    live forex rates scraped from aastock.com (morningstar backdoor)
    """

    uri = "http://www.aastocks.com/en/resources/datafeed/getrtcurconvert.ashx?curr="
    symbols = "USDCNY,USDEUR,USDGBP,USDKRW,USDJPY,USDXAU,USDXAG"
    url = uri + symbols

    try:
        raw = requests.get(url).json()
        data = {}
        for item in raw:
            if item["to"] == "USD":
                if item["from"] in ["XAU", "XAG"]:
                    data[item["to"] + ":" + item["from"]] = 1 / float(item["price"])
            else:
                data[item["symbol"].replace("USD", "USD:")] = float(item["price"])
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))


def ino(site):
    """
    live forex rates scraped from ino.com
    """
    uri = "https://assets.ino.com/data/history/"

    try:
        data = {}
        symbols = ["CNY", "RUB", "EUR", "JPY", "KRW", "GBP"]
        for symbol in symbols:
            query = f"?s=FOREX_USD{symbol}&b=&f=json"
            url = uri + query
            ret = requests.get(url, timeout=(15, 15)).json()[-1][-2]
            data["USD:" + symbol] = float(ret)
        symbols = ["XAG", "XAU"]
        for symbol in symbols:
            query = f"?s=FOREX_{symbol}USDO&b=&f=json"
            url = uri + query
            ret = requests.get(url, timeout=(15, 15)).json()[-1][-2]
            data["USD:" + symbol] = 1 / float(ret)
        data = refine_data(data)
        print(it("purple", "FOREX SCRAPE:"), site, data)
        race_write(f"{site}_forex.txt", json_dumps(data))
    except:
        print(it("purple", "FOREX SCRAPE:"), it("red", f"{site} failed to load"))
