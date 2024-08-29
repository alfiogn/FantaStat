from driver import Driver, FANTASTAT_PATH, HOME, DATA_PATH
from player import Player

import os, glob, re, pickle, time, pdb
import numpy as np

SAFARI = False
EDGE = False
FIREFOX = False
if os.name == 'posix':
    SAFARI = True
elif os.name == 'nt':
    EDGE = True
else:
    FIREFOX = True

SEASON = lambda n: '20%d-%d' % (n, n + 1)
LIST_NAME = lambda s: 'list' + s + '.csv'
PLAYER_LIST_NAME = lambda s: 'players' + s + '.pickle'
QUOT_URL = 'https://www.fantacalcio.it/quotazioni-fantacalcio'

class Scraper():
    def __init__(self, n_years=2):
        self.browser = Driver(safari=SAFARI, edge=EDGE, firefox=FIREFOX)
        self.online = False
        if not os.path.isdir(DATA_PATH):
            os.mkdir(DATA_PATH)
        self.cur_year = int(str(time.gmtime().tm_year)[-2:])
        if time.gmtime().tm_mon < 8:
            self.cur_year -= 1
        self.years_to_analyse = n_years
        self.url_list = None
        self.player_list = None

    def CheckOnline(self, url=QUOT_URL):
        if not self.online:
            self.browser.Get(url)
            self.browser.CookiesAccept()
            self.online = True

    def ScrapPlayerList(self):
        self.url_list = {}
        for y in range(self.cur_year - self.years_to_analyse, self.cur_year + 1):
            season = SEASON(y)
            filename = os.path.join(DATA_PATH, LIST_NAME(season))
            if os.path.isfile(filename):
                self.url_list[season] = np.loadtxt(filename, dtype=str)
            else:
                self.CheckOnline()
                self.url_list[season] = []
                self.browser.Click('//select/option[@value="%s"]' % (season.replace('-', '/')))
                time.sleep(1)
                player_rows = self.browser.Find("//tr[contains(@class, 'player-row')]", False)
                for p in player_rows:
                    up = self.browser.FindIn(p, ".//a[@class='player-name player-link']")
                    link = up.get_attribute('href')
                    if link.split('/')[-1] != season:
                        link += '/' + season
                    link += '/statistico'
                    self.url_list[season].append(link)
                np.savetxt(filename, self.url_list[season], fmt='%s')
            print("Found", len(self.url_list[season]), "players for season", season)
        print("\n")

    def ScrapPlayerData(self):
        self.player_list = {}
        for s in self.url_list.keys():
            print('Season', s)
            backup_file = os.path.join(DATA_PATH, PLAYER_LIST_NAME(s))
            self.player_list[s] = []
            if os.path.isfile(backup_file):
                self.player_list[s] = pickle.load(open(backup_file, 'rb'))

            n = len(self.url_list[s])
            m = len(self.player_list[s])
            player_urls = []
            if m > 0:
                player_urls = [p.url for p in self.player_list[s]]
            if n != m:
                self.CheckOnline()
                error = False
                for i,u in enumerate(self.url_list[s]):
                    if (i < m and not player_urls[i] == u) or u not in player_urls:
                        print('player %d/%d =' % (i + 1, n), u)
                        p = Player(u)
                        try:
                            p.Scrap(self.browser)
                        except:
                            error = True
                            break
                        self.player_list[s].append(p)
                        # pdb.set_trace()
                pickle.dump(self.player_list[s], open(backup_file, 'wb'))
                if error:
                    raise RuntimeError("Error occurred at scraping of player", u)
            print("Scrapped", len(self.player_list[s]), "players for season", s)
        print("\n")

    def ScrapAll(self):
        self.ScrapPlayerList()
        self.ScrapPlayerData()


if __name__ == "__main__":
    scrap = Scraper()
    scrap.ScrapAll()



