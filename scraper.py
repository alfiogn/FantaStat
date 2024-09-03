from driver import Driver, FANTASTAT_PATH, HOME, DATA_PATH
from player import Player, PlayerList

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
        self.browser = None
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
        if self.browser is None:
            self.browser = Driver(safari=SAFARI, edge=EDGE, firefox=FIREFOX)
        if not self.online:
            self.browser.Get(url)
            self.browser.CookiesAccept()
            self.online = True

    def ScrapPlayerList(self, update=False):
        self.url_list = {}
        self.name_list = {}
        for y in range(self.cur_year - self.years_to_analyse, self.cur_year + 1):
            season = SEASON(y)
            filename = os.path.join(DATA_PATH, LIST_NAME(season))
            if os.path.isfile(filename) and not (update and y == self.cur_year):
                self.url_list[season] = np.loadtxt(filename, dtype=str, delimiter=',')
            else:
                self.CheckOnline()
                self.url_list[season] = []
                self.browser.Click('//select/option[@value="%s"]' % (season.replace('-', '/')))
                time.sleep(1)
                player_rows = self.browser.Find("//tr[contains(@class, 'player-row')]", False)
                for p in player_rows:
                    up = self.browser.FindIn(p, ".//a[@class='player-name player-link']")
                    name = self.browser.FindIn(up, ".//span").get_attribute("textContent")
                    link = up.get_attribute('href')
                    if link.split('/')[-1] != season:
                        link += '/' + season
                    link += '/statistico'
                    self.url_list[season].append([name, link])
                np.savetxt(filename, self.url_list[season], fmt='%s,%s')
            print("Found", len(self.url_list[season]), "players for season", season)
        print("\n")

    def ScrapPlayerData(self, update=False):
        self.player_list = {}
        for s in self.url_list.keys():
            print('Season', s)
            backup_file = os.path.join(DATA_PATH, PLAYER_LIST_NAME(s))
            player_list = []
            if os.path.isfile(backup_file) and not (update and s == SEASON(self.cur_year)):
                player_list = pickle.load(open(backup_file, 'rb'))

            n = len(self.url_list[s])
            m = len(player_list)
            player_urls = []
            if m > 0:
                player_urls = [p.url for p in player_list]
            if n != m:
                self.CheckOnline()
                error = False
                index_to_del = []
                for i,(name,u) in enumerate(self.url_list[s]):
                    if (i < m and not player_urls[i] == u) or u not in player_urls:
                        print('player %d/%d =' % (i + 1, n), u)
                        p = Player(u)
                        ok = False
                        try:
                            ok = p.Scrap(self.browser)
                        except:
                            error = True
                            break
                        player_urls.insert(i, p.url)
                        player_list.insert(i, p)
                        if not ok:
                            print("    not found")
                            index_to_del.append(i)
                            m += 1
                        # pdb.set_trace()
                player_list = player_list[:n]
                pickle.dump(player_list, open(backup_file, 'wb'))
                if error:
                    raise RuntimeError("Error occurred at scraping of player", u)
            self.player_list[s] = PlayerList(self.url_list[s], player_list)
            print("Scrapped", len(player_list), "players for season", s)
        print("\n")

    def ScrapAll(self, updatelist=False, updatedata=False):
        self.ScrapPlayerList(updatelist)
        self.ScrapPlayerData(updatedata)

    def UpdateAll(self):
        for s in self.player_list.keys():
            backup_file = os.path.join(DATA_PATH, PLAYER_LIST_NAME(s))
            player_list = []
            for p in self.player_list[s].raw_data:
                if p.name is not None:
                    # put something you want to adjust
                    # eg: p.days = [int(i) for i in p.days]
                    # eg: p._derived()
                    p._derived()
                    pass
                player_list.append(Player(copy=p))
            self.player_list[s] = PlayerList(self.url_list[s], player_list)
            print("Updated", len(player_list), "players for season", s)
            pickle.dump(player_list, open(backup_file, 'wb'))

    def __getitem__(self, key):
        return self.player_list[SEASON(self.cur_year + key)]

    def __len__(self):
        return len(self.player_list)

    def __iter__(self):
        return self.player_list.items()


if __name__ == "__main__":
    scrap = Scraper()
    scrap.ScrapAll()



