import os, glob, re, pickle, time, pdb
import numpy as np
import pandas as pd

TEAM_COLORS = {
    'Atalanta': ('#2d5cae', '#000000'),
    'Bologna': ('#9f1f33', '#1b2838'),
    'Cagliari': ('#98142b', '#ffffff'),
    'Como': ('#1c2a40', '#ffffff'),
    'Cremonese': ('#c9974e', '#e61b23'),
    'Empoli': ('#0558ac', '#ffffff'),
    'Fiorentina': ('#50408f', '#ffffff'),
    'Frosinone': ('#c7d5eb', '#004292'),
    'Genoa': ('#ad0b16', '#002039'),
    'Inter': ('#001ea0', '#000000'),
    'Juventus': ('#000000', '#ffffff'),
    'Lazio': ('#85d8f8', '#000000'),
    'Lecce': ('#db2d1f', '#f6ea00'),
    'Milan': ('#ce171f', '#231f20'),
    'Monza': ('#dd032e', '#ffffff'),
    'Napoli': ('#199fd6', '#003e81'),
    'Parma': ('#FFD200', '#1B4094'),
    'Roma': ('#fbba00', '#970a2c'),
    'Salernitana': ('#651911', '#ffffff'),
    'Sampdoria': ('#004b95', '#ffffff'),
    'Sassuolo': ('#0fa653', '#ffffff'),
    'Spezia': ('#000000', '#a79256'),
    'Torino': ('#881f19', '#ffffff'),
    'Udinese': ('#7f7f7f', '#ffffff'),
    'Venezia': ('#436817', '#EF7D00'),
    'Verona': ('#002d6c', '#f7ca00'),
}

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
    def __init__(self, url='', copy=None):
        if copy is None:
            self.url = url
            self.name = None
            self.team = None
            self.role = None
            self.mantra_role = None
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
            self.presence = None
            self.days = None
            self.matches = None
            self.in_out = None
            self.events = None
            self.matches = None
            self.in_out = None
            self.events = None
            self.long_descr = None
            # derived
            self.db_columns = None
            self.db = None
        else:
            self._copy(copy)
            if self.db is not None:
                self._derived()

    def _copy(self, copy):
        for k,v in copy.__dict__.items():
            exec('self.%s = v' % k)

    def Scrap(self, b):
        b.Get(self.url)
        if '404' in b.instance.current_url:
            return False
        id_content = b.Find("//div[@id='content']", wait=2)
        # time.sleep(0.5)
        if any([i is None for i in [self.name, self.role, self.mantra_role, self.generic_data, self.mv, self.fmv, self.quotc, self.fvmc, self.fvmm, self.descr]]):
            self._main_info(b, id_content)
        if self.stats is None:
            self._summary_stats(b, id_content)
        if any([i is None for i in [self.voto, self.fvoto]]):
            self._grades_graph(b, id_content)
        if any([i is None for i in [self.bonus, self.malus]]):
            self._bonus_malus(b, id_content)
        if self.price is None:
            self._price_graph(b, id_content)
        if any([i is None for i in [self.presence_type, self.matches, self.in_out, self.events]]):
            self._season_table(b, id_content)
        if self.long_descr is None:
            self._last_section(b, id_content)
        self._derived()
        return True

    def _main_info(self, b, parent):
        #
        main_info = b.FindIn(parent, "//section[@id='player-main-info']")
        self.name = b.FindIn(main_info, ".//h1[contains(@class, 'player-name')]").get_attribute("textContent")
        self.team = strip(b.FindIn(main_info, ".//a[contains(@class, 'team-name')]").get_attribute("textContent"))
        self.role = b.FindIn(main_info, ".//span[@class='role']").get_attribute('data-value').title()
        self.mantra_role = b.FindIn(main_info, ".//span[contains(@class, 'role-mantra')]").get_attribute('data-value').title()
        self.generic_data = [strip(t.get_attribute("textContent")) for t in b.FindIn(b.FindIn(main_info, ".//dl[@class='player-data']"), ".//dd", False)]
        self.mv = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Media Voto')]//span[contains(@class, 'badge')]").get_attribute("textContent")))
        self.fmv = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Fantamedia')]//span[contains(@class, 'badge')]").get_attribute("textContent")))
        self.quotc = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Quotazione classic')]//span[contains(@class, 'badge')]").get_attribute("textContent")), int)
        self.quotm = number(strip(b.FindIn(main_info, ".//li[contains(@title, 'Quotazione Mantra')]//span[contains(@class, 'badge')]").get_attribute("textContent")), int)
        self.fvmc =  number(strip(b.FindIn(main_info, ".//li[contains(@title, 'FantaValore di Mercato (Classic)')]//span[contains(@class, 'badge')]").get_attribute("textContent")), int)
        self.fvmm =  number(strip(b.FindIn(main_info, ".//li[contains(@title, 'FantaValore di Mercato (Mantra)')]//span[contains(@class, 'badge')]").get_attribute("textContent")), int)
        try:
            self.descr = b.FindIn(main_info, ".//div[@class='description']").get_attribute("textContent")
        except:
            self.descr = ''
        # print(name, role, mantra_role, generic_data, mv, fmv, quotc, quotm, fvmc, fvmm, descr)

    def _summary_stats(self, b, parent):
        #
        summary_stats = b.FindIn(parent, "//section[@id='player-summary-stats']")
        stats_cont = b.FindIn(summary_stats, ".//tr[@itemprop='variableMeasured']", False)
        self.stats = {}
        for s in stats_cont:
            key = b.FindIn(s, ".//th[@itemprop='name description']").get_attribute("textContent")
            val = strip(b.FindIn(s, ".//td[@class='value']").get_attribute("textContent"))
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

    def _grades_graph(self, b, parent):
        #
        grades_graph = b.FindIn(parent, "//section[@id='player-grades-graph']")
        grades = b.FindIn(grades_graph, ".//div[@class='x-axis']/span", False)
        self.voto, self.fvoto = [], []
        for g in grades:
            self.voto.append(number(g.get_attribute('data-primary-value')))
            self.fvoto.append(number(g.get_attribute('data-secondary-value')))
        # print(voto, fvoto)

    def _bonus_malus(self, b, parent):
        #
        bonus_malus = b.FindIn(parent, "//section[@id='player-bonuses-graph']")
        bolus = b.FindIn(bonus_malus, ".//div[@class='x-axis']/span", False)
        self.bonus, self.malus = [], []
        for bm in bolus:
            self.bonus.append(number(bm.get_attribute('data-primary-value')))
            self.malus.append(number(bm.get_attribute('data-secondary-value')))
        # print(bonus, malus)

    def _price_graph(self, b, parent):
        #
        price_graph = b.FindIn(parent, "//section[@id='player-price-graph']")
        prices = b.FindIn(price_graph, ".//div[@class='x-axis']/span", False)
        self.price = []
        for p in prices:
            self.price.append(number(p.get_attribute('data-primary-value'), int))
        # print(price)

    def _season_table(self, b, parent):
        #
        season_table = b.FindIn(parent, "//section[@id='player-season-table']")
        labels = [
            strip(b.FindIn(i, ".//span[@itemprop='name description']").get_attribute("textContent"))
            for i in b.FindIn(season_table, ".//ul[@class='donut-summary']/li", False)
        ]
        self.presence_type = [
            labels[number(i.get_attribute('class').split(' ')[-1].split('-')[-1], int)]
            for i in b.FindIn(season_table, ".//ul[@class='dot-stripe']/li[contains(@class, 'player-status')]", False)
        ]
        days_summary = b.FindIn(season_table, ".//table[@class='player-summary-table']/tbody/tr[not(contains(@class, 'divider'))]", False)
        self.days = []
        self.matches = []
        self.in_out = []
        self.events = []
        for d in days_summary:
            self.days.append(number(b.FindIn(d, ".//th/span[contains(@class, 'matchweek')]").get_attribute("textContent"), int))
            mtc = b.FindIn(d, ".//td/a[contains(@class, 'match')]")
            home = strip(b.FindIn(mtc, ".//span[contains(@class, 'team-home')]").get_attribute("textContent"))
            score_home, score_away = strip(b.FindIn(mtc, ".//span[contains(@class, 'match-score')]").get_attribute("textContent")).split('-')
            away = strip(b.FindIn(mtc, ".//span[contains(@class, 'team-away')]").get_attribute("textContent"))
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

    def _last_section(self, b, parent):
        #
        self.long_descr = {}
        try:
            last_section = b.Find(parent, "//section[@id='player-description']")
            entries = b.FindIn(last_section, ".//p[@class='li1']", False)
            for e in entries:
                key = strip(b.FindIn(e, './/strong').get_attribute("textContent"))
                value = strip(e.get_attribute("textContent").replace(key, '')[1:])
                self.long_descr[key] = value
        except:
            pass

    def _derived(self):
        self.db_columns = ['Giornata', 'Presenza', 'Voto', 'Bonus', 'Malus', 'Gol', 'Assist', 'RF', 'RS', 'Minuti', 'Vinto', 'InCasa']
        self.db = pd.DataFrame(columns=self.db_columns)
        if self.days is not None:
            i0 = 0
            for d in self.days:
                i = d - 1
                entry = [d, self.presence_type[i], self.voto[i], self.bonus[i], self.malus[i]]
                gf = self.events[i0].get('Gol segnati', 0)
                a = self.events[i0].get('Assist', 0)
                gs = self.events[i0].get('Gol subiti', 0)
                rf = self.events[i0].get('Rigori segnati', 0)
                rp = self.events[i0].get('Rigori parati', 0)
                rs = self.events[i0].get('Rigori sbagliati', 0)
                entry += [gf - gs, a, rf + rp, rs]
                minuti = 0
                if self.in_out[i0][0] != -1:
                    minuti += self.in_out[i0][0]
                if self.in_out[i0][1] != -1:
                    minuti = self.in_out[i0][1] - minuti
                if minuti == 0 and self.presence_type[i] == 'Entrato':
                    minuti = 90 - self.in_out[i0][1]
                if minuti == 0 and self.presence_type[i] == 'Titolare':
                    minuti = 90
                entry += [minuti]
                casa = 0 if self.team[:3].upper() == self.matches[i0][2] else 1
                win = 0
                gi, go = self.matches[i0][1], self.matches[i0][3]
                if gi == go:
                    win = 0.5
                elif bool(casa and gi > go) != bool(not casa and go > gi):
                    win = 1
                entry += [win, casa]
                self.db.loc[len(self.db.index), :] = entry
                i0 += 1

    def __getitem__(self, key):
        return self.__dict__[key]

    def __len__(self):
        return self.days


class PlayerList():
    def __init__(self, ul, ls):
        self.raw_data = ls
        self.map = {ul[i][0].lower(): i  for i,l in enumerate(ls)}

    def __getitem__(self, key):
        if isinstance(key, str):
            if self.map.get(key.lower()) is None:
                return None
            return self.raw_data[self.map[key.lower()]]
        elif isinstance(key, int):
            return self.raw_data[key]
        else:
            RuntimeError("key", key, "not valid, it must be either str or int")

    def __len__(self):
        return len(self.raw_data)


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



