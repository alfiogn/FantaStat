import os, glob, re, pickle, time, pdb
import numpy as np
import pandas as pd

def strip(s):
    return s.replace('\n', '').strip()

def number(s, t=float):
    if s is None or s in ['', '-', '?']:
        return -1
    try:
        return t(s.replace(',', '.'))
    except:
        return -1

class Player():
    def __init__(self, url):
        self.url = url
        self.name = None
        self.role = None
        self.matra_role = None
        self.generic_data = None
        self.mv = None
        self.fmv = None
        self.quotc = None
        self.quotm = None
        self.fvmc = None
        self.fvmm = None
        self.descr = None
        self.stats = None
        self.voto = None
        self.fvoto = None
        self.voto = None
        self.bonus = None
        self.malus = None
        self.price = None
        self.presence_type = None
        self.matches = None
        self.in_out = None
        self.events = None
        self.matches = None
        self.in_out = None
        self.events = None
        self.long_descr = None

    def Scrap(self, b):
        b.Get(self.url)
        # time.sleep(0.5)
        self._main_info(b)
        self._summary_stats(b)
        self._grades_graph(b)
        self._bonus_malus(b)
        self._price_graph(b)
        self._season_table(b)
        self._last_section(b)

    def _main_info(self, b):
        #
        main_info = b.Find("//section[@id='player-main-info']")
        self.name = b.FindIn(main_info, ".//h1[contains(@class, 'player-name')]").text
        self.role = b.FindIn(main_info, ".//span[@class='role']").get_attribute('data-value').title()
        self.matra_role = b.FindIn(main_info, ".//span[contains(@class, 'role-mantra')]").get_attribute('data-value').title()
        self.generic_data = [strip(t.text) for t in b.FindIn(b.FindIn(main_info, ".//dl[@class='player-data']"), ".//dd", False)]
        self.mv = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Media Voto')]//span[contains(@class, 'badge')]").text))
        self.fmv = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Fantamedia')]//span[contains(@class, 'badge')]").text))
        self.quotc = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Quotazione classic')]//span[contains(@class, 'badge')]").text), int)
        self.quotm = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Quotazione Mantra')]//span[contains(@class, 'badge')]").text), int)
        self.fvmc =  number(strip(b.FindIn(main_info, ".//li[contains(@title, 'FantaValore di Mercato (Classic)')]//span[contains(@class, 'badge')]").text), int)
        self.fvmm =  number(strip(b.FindIn(main_info, ".//li[contains(@title, 'FantaValore di Mercato (Mantra)')]//span[contains(@class, 'badge')]").text), int)
        try:
            self.descr = b.FindIn(main_info, ".//div[@class='description']").text
        except:
            self.descr = ''
        # print(name, role, matra_role, generic_data, mv, fmv, quotc, quotm, fvmc, fvmm, descr)

    def _summary_stats(self, b):
        #
        summary_stats = b.Find("//section[@id='player-summary-stats']")
        stats_cont = b.FindIn(summary_stats, ".//tr[@itemprop='variableMeasured']", False)
        self.stats = {}
        for s in stats_cont:
            key = b.FindIn(s, ".//th[@itemprop='name description']").text
            val = strip(b.FindIn(s, ".//td[@class='value']").text)
            self.stats[key] = val
        for k,v in self.stats.items():
            if '/' in k:
                if v[-2:] != '/0':
                    exec('self.stats[k] = float(%s)' % v)
                else:
                    self.stats[k] = -1
            else:
                self.stats[k] = number(v, int)
        # print(stats)

    def _grades_graph(self, b):
        #
        grades_graph = b.Find("//section[@id='player-grades-graph']")
        grades = b.FindIn(grades_graph, ".//div[@class='x-axis']/span", False)
        self.voto, self.fvoto = [], []
        for g in grades:
            self.voto.append(number(g.get_attribute('data-primary-value')))
            self.fvoto.append(number(g.get_attribute('data-secondary-value')))
        # print(voto, fvoto)

    def _bonus_malus(self, b):
        #
        bonus_malus = b.Find("//section[@id='player-bonuses-graph']")
        bolus = b.FindIn(bonus_malus, ".//div[@class='x-axis']/span", False)
        self.bonus, self.malus = [], []
        for bm in bolus:
            self.bonus.append(number(bm.get_attribute('data-primary-value')))
            self.malus.append(number(bm.get_attribute('data-secondary-value')))
        # print(bonus, malus)

    def _price_graph(self, b):
        #
        price_graph = b.Find("//section[@id='player-price-graph']")
        prices = b.FindIn(price_graph, ".//div[@class='x-axis']/span", False)
        self.price = []
        for p in prices:
            self.price.append(number(p.get_attribute('data-primary-value'), int))
        # print(price)

    def _season_table(self, b):
        #
        season_table = b.Find("//section[@id='player-season-table']")
        labels = [
            strip(b.FindIn(i, ".//span[@itemprop='name description']").text)
            for i in b.FindIn(season_table, ".//ul[@class='donut-summary']/li", False)
        ]
        self.presence_type = [
            labels[number(i.get_attribute('class').split(' ')[-1].split('-')[-1], int)]
            for i in b.FindIn(season_table, ".//ul[@class='dot-stripe']/li[contains(@class, 'player-status')]", False)
        ]
        days_summary = b.FindIn(season_table, ".//table[@class='player-summary-table']/tbody/tr[not(contains(@class, 'divider'))]", False)
        self.matches = []
        self.in_out = []
        self.events = []
        for d in days_summary:
            mtc = b.FindIn(d, ".//td/a[contains(@class, 'match')]")
            home = strip(b.FindIn(mtc, ".//span[contains(@class, 'team-home')]").text)
            score_home, score_away = strip(b.FindIn(mtc, ".//span[contains(@class, 'match-score')]").text).split('-')
            away = strip(b.FindIn(mtc, ".//span[contains(@class, 'team-away')]").text)
            self.matches.append([home, int(score_home), away, int(score_away)])

            self.in_out.append([
                number(b.FindIn(d, ".//td/span[@class='sub-in']").get_attribute('data-minute'), int),
                number(b.FindIn(d, ".//td/span[@class='sub-out']").get_attribute('data-minute'), int)
            ])

            evs = b.FindIn(d, ".//td/span[@class='events']/figure", False)
            evd = {}
            for e in evs:
                evd[e.get_attribute('title')] = number(e.get_attribute('data-value'), int)
            self.events.append(evd)
        # print(presence_type, matches, in_out, events, sep='\n')

    def _last_section(self, b):
        #
        last_section = b.Find("//section[@id='player-description']")
        self.long_descr = {}
        entries = b.FindIn(last_section, ".//p[@class='li1']", False)
        for e in entries:
            key = strip(b.FindIn(e, './/strong').text)
            value = strip(e.text.replace(key, '')[1:])
            self.long_descr[key] = value


if __name__ == "__main__":
    from driver import Driver
    from scraper import SAFARI, EDGE, FIREFOX
    url = 'https://www.fantacalcio.it/serie-a/squadre/atalanta/retegui/6228/2024-25/statistico'
    pl = Player(url)
    b = Driver(SAFARI, EDGE, FIREFOX)
    b.Get(url)
    b.CookiesAccept()
    pl.Scrap(b)
    for k,v in pl.__dict__.items():
        print(k, "=", v)



