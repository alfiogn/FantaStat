import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.io as pio
pio.templates.default = 'ggplot2'

from selenium.webdriver.common.by import By

import os, re, pdb, unicodedata, time, glob
import pickle
from difflib import get_close_matches

NTEAMS = 20
NDAYS = 38
NAMES_REGEX = "([A-Z][a-z']*[A-Z][a-z]*|[A-Z][a-z]* [A-Z][a-z]*|[A-Z][a-z]*)/([A-Z][a-z']*[A-Z][a-z]*|[A-Z][a-z]* [A-Z][a-z]*|[A-Z][a-z]*)?"

def ReadExcel(f, **kwargs):
    print("Opening file ", f)
    if f.endswith('.xlsx'):
        return pd.read_excel(f, engine='openpyxl', **kwargs)
    elif f.endswith('.xls'):
        return pd.read_excel(f, engine='xlrd', **kwargs)
    else:
        raise RuntimeError('format of %f not recognised')

def MatchPlayer(n, t, db):
    possible_names = db.loc[db['Squadra'].values == t, 'Nome'].values
    closest = get_close_matches(n, possible_names, n=1)
    if len(closest) == 0:
        closest = get_close_matches(n, possible_names, n=1, cutoff=0.3)
    return db[db['Nome'] == closest[0]].index.values

def MatchPlayerList(n, t, db):
    possible_names = db.loc[db['Squadra'].values == t, 'Nome'].values
    idx = []
    for i in n:
        closest = get_close_matches(i, possible_names, n=1)
        if len(closest) == 0:
            closest = get_close_matches(i, possible_names, n=1, cutoff=0.3)
        if len(closest) == 0:
            print(t, possible_names, i, closest)
        idx += [db[db['Nome'] == closest[0]].index.values]
    return idx



class championship():
    def __init__(self, y, b, url, prefix, present=False):
        self.map = lambda x: np.array(
            x.replace('[', '').replace(']', '').replace(',', '').split(),
            dtype=int)
        self.year = y
        self.url = url
        self.db = None
        self.toRead = True
        self.MeanByTeam = None
        self.GolSumByTeam = None
        self.GolNegByTeam = None
        self.browser = b
        self.filebase = prefix + '20' + str(y) + '.csv'
        self.file = '/'.join([b.download_path, self.filebase])
        self.last_day = NDAYS
        if b.CheckData(self.filebase):
            if not b.CheckTimeStamp(self.filebase, days=2) or not present:
                self.db = pd.read_csv(self.file).map(self.map)
                self.last_day = self.db.shape[0]
                self.toRead = False

        if self.toRead:
            self.ScrapAll()

    def ScrapDay(self):
        home = self.browser.find_elements(By.XPATH, "//div[contains(@class, 'hm-name-team home')]")
        scores = self.browser.find_elements(By.XPATH, "//div[contains(@class, 'hm-marker-box')]")
        out = self.browser.find_elements(By.XPATH, "//div[contains(@class, 'hm-name-team away')]")
        data = np.empty((len(home), 4), dtype='<U20')
        for i in range(len(home)):
            data[i, 0] = home[i].text
            data[i, 2] = out[i].text
        count = 0
        for i in range(len(scores)):
            if re.match(re.compile('[0-9]-[0-9]'), scores[i].text):
                data[count, [1, 3]] = scores[i].text.split('-')
                count += 1
        return data

    def ScrapAll(self):
        self.browser.get(self.url)
        self.browser.Click("//button[contains(., 'Accetta')]")
        y = None
        count = 0
        while y is None and count < 15:
            time.sleep(0.25)
            y = self.browser.find_elements(By.XPATH, "//option[contains(., '20%d-%d')]" % (self.year, self.year+1))[0]
            count += 1
        if y.get_property('selected') is None:
            try:
                y.click()
            except:
                RuntimeError("Year 20%d-%d not found at %s" % (self.year, self.year+1, self.browser.current_url), y)
        time.sleep(1)
        # self.browser.refresh()
        df = pd.DataFrame(data=[[np.zeros(3, dtype=int)]*NTEAMS]*NDAYS)
        print("Scraping year", self.year)

        teams = []
        bdays = []
        time.sleep(2)
        count = 0
        while len(bdays) == 0 and count < 15:
            time.sleep(0.25)
            bdays = self.browser.find_elements(By.XPATH, "//option[contains(., 'Giornata')]")
            count += 1
        for i in range(NDAYS):
            if i > (len(bdays) - 1):
                RuntimeWarning("Day %d of year %d missing" % (i + 1, self.year))
                continue
            bdays[i].click()
            time.sleep(1.0)
            home_out = self.ScrapDay()
            print("day", i+1)

            if i == 0:
                teams = np.append(home_out[:, 0], home_out[:, 2])
                teams.sort()
                df.columns = teams

            # pdb.set_trace()
            if np.all(home_out[:, 1] == ''):
                df = df.iloc[:i, :]
                self.last_day = i + 1
                break

            # try:
            for j in range(home_out.shape[0]):
                team_out = np.where(teams == home_out[j, 2])[0][0]
                ghome = home_out[j, 1]
                df.loc[i, home_out[j, 0]] = [1, 0 if ghome == '' else int(ghome), team_out]
                team_home = np.where(teams == home_out[j, 0])[0][0]
                gout = home_out[j, 3]
                df.loc[i, home_out[j, 2]] = [0, 0 if gout == '' else int(gout), team_home]
            # except:
            #     RuntimeError(home_out)

        df.to_csv(self.file, index=False)
        self.db = df

    def GetEnglishMean(self):
        if self.MeanByTeam is None:
            self.EnglishMean()
        return self.MeanByTeam

    def GetGolSum(self):
        if self.GolSumByTeam is None:
            self.EnglishMean()
        return self.GolSumByTeam

    def GetGolNeg(self):
        if self.GolNegByTeam is None:
            self.EnglishMean()
        return self.GolNegByTeam

    def EnglishMean(self):
        ndays = self.last_day
        ndays = self.db.shape[0]
        values = pd.DataFrame(np.zeros((ndays, NTEAMS)), columns=self.db.columns)
        golsum = pd.DataFrame(np.zeros((ndays, NTEAMS)), columns=self.db.columns)
        golneg = pd.DataFrame(np.zeros((ndays, NTEAMS)), columns=self.db.columns)
        for i in range(ndays):
            dayi = np.vstack(self.db.iloc[i, :].values)
            casa = dayi[:, 0]
            vittoria = dayi[:, 1] > dayi[dayi[:, -1], 1]
            sconfitta = dayi[:, 1] < dayi[dayi[:, -1], 1]
            pareggio = dayi[:, 1] == dayi[dayi[:, -1], 1]
            values.iloc[i, vittoria] += casa[vittoria]
            values.iloc[i, sconfitta] += (-casa[sconfitta] - 1)
            values.iloc[i, pareggio] -= casa[pareggio]
            golsum.iloc[i, :] = dayi[:, 1]
            golneg.iloc[i, :] = dayi[dayi[:, -1], 1]

        self.MeanByTeam = np.cumsum(values)
        self.GolSumByTeam = np.cumsum(golsum)
        self.GolNegByTeam = np.cumsum(golneg)


class PlayersList():
    def __init__(self, b, y, prob=None, rig=None, approb=None, backup=None,
                 prefix='quotazioni', stat='statistiche', offset=0):
        self.year = y
        self.browser = b
        self.proburl = prob
        self.approburl = approb
        self.rigurl = rig
        self.filebaseq = prefix + '20' + str(y) + '.xlsx'
        self.filebases = stat + '20' + str(y) + '.xlsx'
        self.offset = offset
        self.filebaseold = stat + '20' + str(y-offset) + '.xlsx'
        self.newteams = []
        self.fileq = '/'.join([b.download_path, self.filebaseq])
        self.files = '/'.join([b.download_path, self.filebases])
        self.fileold = '/'.join([b.download_path, self.filebaseold])
        self.db = None
        if backup is None:
            self.backupfilebase = 'backup_players_'+'20'+str(y)+'.pickle'
        else:
            self.backupfilebase = 'backup_players_'+'20'+str(y)+'_'+backup+'.pickle'
        self.backupfile = '/'.join([b.download_path, self.backupfilebase])
        self.Loaded = False
        if b.CheckData(self.backupfilebase):
            if not b.CheckTimeStamp(self.backupfilebase, days=2):
                with open(self.backupfile, 'rb') as f:
                    self.db = pd.read_pickle(f)
                    self.Loaded = True
        self.Read()

    def Read(self):
        if not self.Loaded:
            # Tutti e Ceduti
            df = ReadExcel(self.fileq, sheet_name='Tutti', skiprows=1)

            # check for non mantra values
            idx = []
            for i,c in enumerate(df.columns):
                if c[-2:] != ' M' and c[:4] != 'Diff':
                    idx += [i]
            self.db = df.iloc[:, idx]
            self.db = self.AddStats(self.db)
            day = 0
            if self.approburl is not None:
                self.GetAPrioriPriorities(self.approburl)
            if self.proburl is not None:
                day = self.GetPriorities(self.proburl)
                if day != 0:
                    with open('/'.join([self.browser.download_path,
                                        'prob_form_20'+str(self.year)+'_'+str(day)+'.pickle']), 'wb') as f:
                        pickle.dump(self.db[['Nome', 'Squadra', 'N.Tit', 'N.Sos']], f)
                    iidx = np.zeros(self.db.shape[0], dtype=int)
                    for i in range(day, 0, -1):
                        dfi = pd.read_pickle(
                            open('/'.join([self.browser.download_path,
                                           'prob_form_20'+str(self.year)+'_'+str(i)+'.pickle']), 'rb'),
                        )
                        for i in range(self.db.shape[0]):
                            ii = np.where(self.db['Nome'].values[i] == dfi['Nome'].values)[0]
                            if len(ii) == 0:
                                continue
                            else:
                                ii = ii[0]
                            if dfi['N.Tit'].values[ii] != '':
                                iidx[i] += int(dfi['N.Tit'].values[ii])
                            else:
                                iidx[i] += 3
                                # if dfi['N.Sos'].values[ii] != '':
                                #     self.db.loc[i, 'N.Sos'] += ',' + dfi['N.Sos'].values[ii]

                    self.db['N.Tit'] = np.round(iidx/day, 1)
                    self.db['N.Tit'].values[iidx/day > 2.99] = 0

            if self.rigurl is not None:
                self.GetPenalties(self.rigurl)

            self.SimplifyDB()

            with open(self.backupfile, 'wb') as f:
                pickle.dump(self.db, f)
                self.Loaded = True

    def SimplifyDB(self):
        if 'FVM' in self.db.columns:
            self.db.FVM = np.round(self.db.FVM/1000.0*500.0)
        qti = ''
        if 'Qt. I' in self.db.columns:
            qti = 'Qt. I'
            self.db['Qt. I'] = self.db['Qt. A'] - self.db['Qt. I']
        if 'Qt.I' in self.db.columns:
            qti = 'Qt.I'
            self.db['Qt.I'] = self.db['Qt.A'] - self.db['Qt.I']
        self.db['Rp'] += self.db['Rc']
        self.db['Esp'] += self.db['Amm']/2.0
        self.db['Gf'] -= self.db['Gs']
        # rename columns
        self.db.rename(columns={qti:'Qt.Diff', 'FVM':'FVM', 'Rp':'Rigori', 'Esp':'Malus'}, inplace=True)
        # delete useless
        todel = ['R-', 'R+', 'Au', 'Rc', 'Amm', 'Gs']
        if np.sum(self.db['Qt.Diff']) < 1e-10:
            todel += ['Qt.Diff']
        self.db.drop(columns=todel, inplace=True)

    def AddStats(self, fdb):
        # Tutti e Ceduti
        df = ReadExcel(self.files, sheet_name='Tutti', skiprows=1)
        dfold = None
        if self.offset > 0:
            dfold = ReadExcel(self.fileold, sheet_name='Tutti', skiprows=1)
            teams = df['Squadra'].unique()
            teamsold = dfold['Squadra'].unique()
            for i in teams:
                if i in teamsold:
                    self.newteams += [i]

            for i in teamsold:
                if i not in teams:
                    self.newteams += [i]

        df.rename(columns={'Pv':'Pg', 'Fm':'Mf'}, inplace=True)

        df1 = fdb.merge(df, left_on=['Nome'], right_on=['Nome'], suffixes=("", "_y"), how='left')
        df1.drop(columns=['Id', 'Id_y', 'R_y', 'Squadra_y'], inplace=True)
        if dfold is not None:
            dfold.drop(columns=['Id', 'R', 'Squadra'], inplace=True)
            df1 = df1.merge(dfold, left_on=['Nome'], right_on=['Nome'], suffixes=("_x", ""), how='left')
            for i in df1.columns:
                if i[-2:] == '_x':
                    df1.drop(columns=[i], inplace=True)
        return df1.fillna(0)

    def GetPriorities(self, url):
        self.browser.Get(url)
        self.db['N.Tit'] = ''
        self.db['N.Sos'] = ''
        # self.db['Squa'] = ''
        self.db['Inf'] = ''
        day = int(self.browser.find_element(By.XPATH, "//small[contains(., 'Giornata')]").text.split()[-1])
        home = [i.text for i in self.browser.find_elements(By.XPATH, "//label[contains(@class, 'team-home')]")[10:]]
        away = [i.text for i in self.browser.find_elements(By.XPATH, "//label[contains(@class, 'team-away')]")[10:]]
        titlist = self.browser.find_elements(By.XPATH, "//ul[contains(@class, 'player-list starters')]")
        soslist = self.browser.find_elements(By.XPATH, "//ul[contains(@class, 'player-list reserves')]")
        ballolist = self.browser.find_elements(By.XPATH, "//section[contains(@class, 'ballots')]")
        susplist = self.browser.find_elements(By.XPATH, "//section[contains(@class, 'suspendeds')]")
        injlist = self.browser.find_elements(By.XPATH, "//section[contains(@class, 'injureds')]")

        def subIdx(ls, t, col, sub):
            idx = MatchPlayerList(ls, t, self.db)
            if isinstance(sub, list):
                for i,line in enumerate(idx):
                    self.db[col].values[line] = sub[i]
            else:
                for line in idx:
                    self.db[col].values[line] = sub

        print("Scraping priorities:")
        for i in range(len(home)):
            ha_ballo = ballolist[i].find_elements(By.XPATH, ".//div[@class='content']")
            ha_susp = susplist[i].find_elements(By.XPATH, ".//div[@class='content']")
            ha_inj = injlist[i].find_elements(By.XPATH, ".//div[@class='content']")
            ha_team = [home[i], away[i]]
            print(' vs '.join(ha_team))
            for j in range(2):
                ballo, susp, inj = ha_ballo[j], ha_susp[j], ha_inj[j]

                team = ha_team[j].title()
                idx = 2*i + j
                tit = titlist[idx].text.split('\n')[::2]
                subIdx(tit, team, 'N.Tit', 1)
                sos = soslist[idx].text.split('\n')
                for k in sos:
                    if k[:16] == "con quest'ultimo":
                        sos.remove(k)
                sos = sos[::2]
                perc = np.array([int(j.replace('%', ''))
                                   for j in soslist[idx].text.split('\n')[1::2]])
                sos = np.array(sos)[perc > 30]
                subIdx(sos, team, 'N.Tit', 2)
                firsts = ballo.text.split('\n')
                for k in firsts:
                    if k[:16] == "con quest'ultimo":
                        firsts.remove(k)
                firsts = firsts[::2][::2]
                if firsts[0][:6] != 'Nessun':
                    seconds = ballo.text.split('\n')
                    for k in seconds:
                        if k[:16] == "con quest'ultimo":
                            seconds.remove(k)
                    seconds = seconds[::2][1::2]
                    subIdx(seconds, team, 'N.Tit', 2)
                    subIdx(seconds, team, 'N.Sos', firsts)
                injpl = inj.text.split('\n')[::2]
                if injpl[0][:6] != 'Nessun':
                    injreason = inj.text.split('\n')[1::2]
                    injre = []
                    for l in injreason:
                        lll = l.split(' ')
                        for k in range(len(lll)):
                            if lll[k] == 'rientro':
                                injre += [' '.join(lll[k:])]
                                break
                            if lll[k] == 'sospeso':
                                injre += ['sospeso']
                                break
                            if lll[k] == 'recuperabile':
                                injre += ['rientro']
                                break
                            if lll[k] == 'out' and lll[k+1] in ['contro', 'per', 'a', 'nella']:
                                injre += [' '.join(lll[k:])]
                                break
                            if lll[k] == 'da' and lll[k+1] == 'valutare':
                                injre += [' '.join(lll[k:])]
                                break
                            if lll[k] == 'in' and lll[k+1] == 'dubbio':
                                injre += [' '.join(lll[k:])]
                                break
                    if len(injpl) != len(injre):
                        print("Length of", injpl, "different from", injre, "\nfrom:", injreason)
                        # pdb.set_trace()
                    subIdx(injpl, team, 'Inf', injre)
                # h_sq = h_susp.text.split('\n')

        return day


    def GetPenalties(self, url):
        self.browser.Get(url)
        self.db['Rig'] = ''
        self.db['Pun'] = ''
        teams = self.browser.find_elements(By.XPATH, "//div[contains(@id, 'team-')]")
        rigf = lambda nm: '/'.join([str(nm[0]), str(nm[1])])
        print('Scraping penalties:')

        for t in teams:
            text = unicodedata.normalize('NFD', t.text).encode('ascii', 'ignore').decode("utf-8")
            txt = text.replace('*', '').split('\n')
            teamUp = txt[0].title()
            print(teamUp)
            rigdict = {}
            for i in [2, 3, 4]:
                rigdict[txt[i]] = [0, 0]
                rigdict[txt[i + 4]] = [0, 0]
            for i in [2, 3, 4]:
                rigdict[txt[i]][0] = i - 1
                rigdict[txt[i + 4]][1] = i - 1

            idx = MatchPlayerList(rigdict.keys(), teamUp, self.db)
            for i,r in enumerate(rigdict.keys()):
                self.db['Rig'].values[idx[i]] = rigf(rigdict[r]).split('/')[0]
                self.db['Pun'].values[idx[i]] = rigf(rigdict[r]).split('/')[1]


    def GetAPrioriPriorities(self, url):
        self.browser.Get(url)
        teams = self.browser.find_elements(By.XPATH, "//aside[@class='text-type-aside']")
        self.db['AP.Tit'] = ''
        print('Scraping a priori-ties:')

        for t in teams:
            text = unicodedata.normalize('NFD', t.text).encode('ascii', 'ignore').decode("utf-8")
            txt = text.replace('*', '').split('\n')
            teamUp = txt[0].title()
            print(teamUp)
            # team line up
            lineup = txt[3].split(': ')[-1][:-1].replace(';', ',').split(', ')
            idx = MatchPlayerList(lineup, teamUp, self.db)
            for i in idx:
                self.db['AP.Tit'].values[i] = '1'
            # substitutes
            ballo = [re.findall(NAMES_REGEX, i)[0] for i in txt[4].split(';')]
            firsts = [i[0] for i in ballo]
            seconds = [i[-1] for i in ballo]
            idx = MatchPlayerList(seconds, teamUp, self.db)
            for j,i in enumerate(idx):
                self.db['AP.Tit'].values[i] = firsts[j]





class Archive():
    def __init__(self, y0, y1, b, url, last=None, prob=None, rig=None, approb=None, prefix='archivio'):
        self.year0 = y0
        self.year1 = y1
        self.url = url
        self.proburl = prob
        self.approburl = approb
        self.rigurl = rig
        self.browser = b
        self.download_path = b.download_path
        self.prefix = prefix
        self.Story = []
        self.Players = []
        self.Present = None
        self.PresentTeams = None
        self.PresentPlayersAndStats = None
        # last days data
        self.LastDays = last
        self.LastKey = lambda n0, n1: '%d %d' % (n0, n1)
        self.backup_last = '/'.join([b.download_path, 'backup_last_n_days.pickle'])
        self.LastPlayersFiles = None
        self.LastPlayers = None
        self.last_loaded = False
        if os.path.isfile(self.backup_last):
            with open(self.backup_last, 'rb') as f:
                self.LastPlayersFiles, self.LastPlayers = pd.read_pickle(f)
                self.last_loaded = True
        self.LastStats = {}
        self.PlayerStory = {}

        self.GetInfo()

    def GetStory(self):
        for i in range(self.year0, self.year1+1):
            self.Story += [championship(i, self.browser, self.url, self.prefix)]
        self.Present = championship(self.year1+1, self.browser, self.url, self.prefix, present=True)

    def GetPlayers(self):
        for i in range(self.year0, self.year1+1):
            self.Players += [PlayersList(self.browser, i)]
        self.PresentPlayersAndStats = \
                PlayersList(self.browser, self.year1+1, approb=self.approburl,
                            backup='stats', prob=self.proburl, rig=self.rigurl)
        self.PresentTeams = self.PresentPlayersAndStats.db['Squadra'].unique()

    def PresentGetLastNDays(self, n):
        from .utils import voti_prefix
        files = []
        offset = 1
        while len(files) < n:
            loc_files = glob.glob('/'.join([self.download_path, voti_prefix(self.year1 + offset, '*')]))
            loc_files.sort(key=lambda s: int(re.findall('[0-9]*[0-9]', s)[-1]), reverse=True)
            files += loc_files
            offset -= 1

        files = files[:n]

        if self.LastPlayers is not None and (self.last_loaded and files[0] in self.LastPlayersFiles):
            return None

        self.LastPlayersFiles = files
        self.LastPlayers = []
        cols = ['Pg', 'Mv', 'Mf', 'Gf', 'Rigori', 'Ass', 'Malus']

        for k,f in enumerate(files):
            print("Reading voti", f)
            # init f-day database
            last_db = self.PresentPlayersAndStats.db.copy()
            last_db.loc[:, cols] = 0
            # read data
            df = ReadExcel(f, sheet_name='Statistico', skiprows=3)
            idx = df['Unnamed: 1'].isnull().values.nonzero()[0]
            for i in range(len(idx)-1):
                team_data = df.iloc[idx[i]:idx[i+1], :]
                team_name = team_data.iloc[0, 0]
                db = team_data.iloc[1:, 1:]
                db1 = db.iloc[1:-1, 1:]
                db1.columns = db.iloc[0, 1:]
                db1.index = list(range(db1.shape[0]))
                for j in range(db1.shape[0]):
                    name = db1.loc[j, 'Nome']
                    try:
                        jdx = np.where(last_db.Nome == name)[0][0]
                        voto, gf, gs, rp, rs, rf, au, amm, esp, ass = db1.iloc[j, 1:]
                        if str(voto)[-1] != '*':
                            pg = 1
                            bonus = gf*3 + ass
                            malus = gs + rp*3 + 0.5*amm + esp

                            last_db.loc[jdx, cols] = [pg, voto, voto+bonus-malus, gf-gs, rf-rs, ass, malus]
                    except:
                        not_found = True

            self.LastPlayers += [last_db]

        with open(self.backup_last, 'wb') as f:
            pickle.dump([self.LastPlayersFiles, self.LastPlayers], f)
            self.last_loaded = True

    def GetLastStats(self, n0=1, n1=20):
        if self.LastStats.get(self.LastKey(n0, n1)) is None:
            cols = ['Pg', 'Mv', 'Mf', 'Gf', 'Rigori', 'Ass', 'Malus']
            self.LastStats[self.LastKey(n0, n1)] = self.PresentPlayersAndStats.db.copy()
            dbn = self.LastStats[self.LastKey(n0, n1)]
            dbn.loc[:, cols] = 0
            ndays = self.LastPlayers[0]['Pg'].values*0.0 + 1e-10
            for dbi in self.LastPlayers[::-1][(n0 - 1):n1]:
                dbn['Pg'] += dbi['Pg']
                ndays += dbi['Pg'].values
                idx = dbi['Pg'] > 0
                dbn.loc[idx, 'Mv']     += dbi.loc[idx, 'Mv']
                dbn.loc[idx, 'Mf']     += dbi.loc[idx, 'Mf']
                dbn.loc[idx, 'Gf']     += dbi.loc[idx, 'Gf']
                dbn.loc[idx, 'Rigori'] += dbi.loc[idx, 'Rigori']
                dbn.loc[idx, 'Ass']    += dbi.loc[idx, 'Ass']
                dbn.loc[idx, 'Malus']  += dbi.loc[idx, 'Malus']
            dbn['Mv'] = np.round(dbn['Mv'].values/ndays, 2)
            dbn['Mf'] = np.round(dbn['Mf'].values/ndays, 2)

        return self.LastStats[self.LastKey(n0, n1)]

    def GetPlayerStory(self, n0=None, n1=None):
        if self.PlayerStory.get(self.LastKey(n0, n1)) is None:
            cols = ['Pg', 'Mv', 'Mf', 'Gf', 'Rigori', 'Ass', 'Malus']
            db = self.PresentPlayersAndStats.db
            n_players = db.shape[0]
            if n0 is None: n0 = 1
            if n1 is None: n1 = len(self.LastPlayers)
            ndays = n1
            mean = np.zeros((n_players, ndays))
            fantamean = np.zeros((n_players, ndays))
            bonus = np.zeros((n_players, ndays))
            for i,dbi in enumerate(self.LastPlayers[::-1][(n0 - 1):n1]):
                mean[:, i]  = dbi['Mv'].values
                fantamean[:, i] = dbi['Mf'].values
                bonus[:, i] = dbi['Mf'].values + dbi['Malus'].values - dbi['Mv'].values

            mean = np.cumsum(mean, axis=1)
            fantamean = np.cumsum(fantamean, axis=1)
            bonus = np.cumsum(bonus, axis=1)
            to_keep = np.where(mean[:, -1] > 1e-10)[0]
            self.PlayerStory[self.LastKey(n0, n1)] = pd.DataFrame(columns=['R', 'Nome', 'Squadra', 'Day', 'Mean', 'FantaMean', 'Bonus'])
            for i in to_keep:
                const_val = db.loc[i, ['R', 'Nome', 'Squadra']].values
                for j in range(ndays):
                    ni = len(self.PlayerStory[self.LastKey(n0, n1)].index)
                    self.PlayerStory[self.LastKey(n0, n1)].loc[ni, :] = \
                            const_val.tolist() + [j + 1, mean[i, j], fantamean[i, j], bonus[i, j]]    #, malus[i, j]]

        return self.PlayerStory[self.LastKey(n0, n1)]

    def GetInfo(self):
        print("Retrieve archive data:")
        self.GetStory()
        print("    - players")
        self.GetPlayers()
        print("    - last days")
        self.PresentGetLastNDays(self.LastDays)
        if self.PresentPlayersAndStats.db.shape[0] != self.LastPlayers[0].shape[0]:
            self.LastPlayers = None
            self.PresentGetLastNDays(self.LastDays)

        # print("    - initialize last days combination")
        # for i in range(self.LastDays - 1):
        #     for j in range(i + 1, self.LastDays):
        #         print("        %d - %d" % (i+1, j+1))
        #         self.GetLastStats(n0=i + 1, n1=j + 1)
        #         self.GetPlayerStory(n0=i + 1, n1=j + 1)


    def TeamColorsDict(self, only_bg=False):
        d1 = {
            'Atalanta': ('#2d5cae', '#000000'),
            'Bologna': ('#9f1f33', '#1b2838'),
            'Cremonese': ('#c9974e', '#e61b23'),
            'Empoli': ('#0558ac', '#ffffff'),
            'Fiorentina': ('#50408f', '#ffffff'),
            'Inter': ('#001ea0', '#000000'),
            'Juventus': ('#000000', '#ffffff'),
            'Lazio': ('#85d8f8', '#000000'),
            'Lecce': ('#db2d1f', '#f6ea00'),
            'Milan': ('#ce171f', '#231f20'),
            'Monza': ('#dd032e', '#ffffff'),
            'Napoli': ('#199fd6', '#003e81'),
            'Roma': ('#fbba00', '#970a2c'),
            'Salernitana': ('#651911', '#ffffff'),
            'Sampdoria': ('#004b95', '#ffffff'),
            'Sassuolo': ('#0fa653', '#ffffff'),
            'Spezia': ('#000000', '#a79256'),
            'Torino': ('#881f19', '#ffffff'),
            'Udinese': ('#7f7f7f', '#ffffff'),
            'Verona': ('#002d6c', '#f7ca00'),
            'Frosinone': ('#c7d5eb', '#004292'),
            'Genoa': ('#ad0b16', '#002039'),
            'Cagliari': ('#98142b', '#ffffff'),
        }
        if only_bg:
            d2 = dict()
            for i in d1.keys():
                d2[i] = d1[i][0]
            return d2
        else:
            return d1

    def TeamColorsList(self, teams, only_bg=True):
        d = self.TeamColorsDict(only_bg=only_bg)
        return [d[t.capitalize()]  for t in teams]

    def TeamColors(self):
        colors_dict = self.TeamColorsDict()
        return [
            {
                'if': {
                    'column_id': 'Squadra',
                    'filter_query': '{{Squadra}} = {}'.format(i),
                },
                'backgroundColor': colors_dict[i][0] + 'B3',
                'color': colors_dict[i][1],
                'fontWeight': 'bold',
            }
            for i in colors_dict.keys()
        ]

    def PlotEnglishMean(self):
        columns = ['Team', 'Year', 'Mean', 'Fatti', 'Subiti']
        df = pd.DataFrame(data=np.empty((0, 5)), columns=columns)
        for i,s in enumerate(self.Story):
            means = s.GetEnglishMean().iloc[-1, :]
            golsum = s.GetGolSum().iloc[-1, :]
            golneg = s.GetGolNeg().iloc[-1, :]
            df0 = pd.DataFrame(data=np.empty((0, 5)), columns=columns)
            df0['Team'] = means.index
            df0['Year'] = self.year0 + i
            df0['Mean'] = means.values
            df0['Fatti'] = golsum.values
            df0['Subiti'] = -golneg.values
            df = pd.concat([df, df0])

        idx = np.full(df.shape[0], 0)
        for i in self.PresentTeams:
            idx += df.Team.values == i.upper()

        idx = idx > 0
        df = df[idx]

        df['Team'] = [t.capitalize() for t in df['Team']]

        color_map = self.TeamColorsDict(only_bg=True) #List(df.team)
        fig0 = px.line(df, x='Year', y='Mean', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title="English mean", line_shape="spline")
        fig1 = px.line(df, x='Year', y='Fatti', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title="Gol fatti", line_shape="spline")
        fig2 = px.line(df, x='Year', y='Subiti', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title="Gol subiti", line_shape="spline")
        # fig.write_html(self.browser.download_path+'/year_means.html')
        return fig0, fig1, fig2

    def PlotEnglishMeanYear(self, y):
        columns = ['Team', 'Day', 'Mean', 'Fatti', 'Subiti']
        means, golsum, golneg = None, None, None
        if (y - self.year0) == len(self.Story):
            means = self.Present.GetEnglishMean()
            golsum = self.Present.GetGolSum()
            golneg = self.Present.GetGolNeg()
        else:
            means = self.Story[y - self.year0].GetEnglishMean()
            golsum = self.Story[y - self.year0].GetGolSum()
            golneg = self.Story[y - self.year0].GetGolNeg()

        df = pd.DataFrame(data=np.empty((0, 5)), columns=columns)
        for i in means.columns:
            df0 = pd.DataFrame(data=np.empty((0, 5)), columns=columns)
            df0['Day'] = means.index
            df0['Day'] += 1
            df0['Team'] = i
            df0['Mean'] = means[i]
            df0['Fatti'] = golsum[i]
            df0['Subiti'] = -golneg[i]
            df = pd.concat([df, df0])

        df['Team'] = [t.capitalize() for t in df['Team']]
        color_map = self.TeamColorsDict(only_bg=True) #List(df.team)
        fig0 = px.line(df, x='Day', y='Mean', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title='English mean per l\'anno 20' + str(y),
                       line_shape="spline")
        fig1 = px.line(df, x='Day', y='Fatti', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title='Gol fatti nell\'anno 20' + str(y),
                       line_shape="spline")
        fig2 = px.line(df, x='Day', y='Subiti', color='Team', markers=True,
                       color_discrete_map=color_map,
                       title='Gol subiti nell\'anno 20' + str(y),
                      line_shape="spline")
        # fig.write_html(self.browser.download_path+'/last_means.html')
        return fig0, fig1, fig2














