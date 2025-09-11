import os
import pandas as pd
import numpy as np
import spire.xls as spx
import spire.xls.common as spxc

from .driver import DATA_DIR
from .scraper import SEASON, Scraper
from .player import Player, PlayerList, TEAM_COLORS

ASTA_BUDGET = 500

class FantaStat():
    def __init__(self, rawdata: Scraper, appunti: str | None=None, dryrun: bool=False, basepath: str='.'):
        self.basepath: str = basepath
        self.dryrun = dryrun
        self.raw: Scraper = rawdata
        self.notes: pd.DataFrame | None = None
        self.cur_db: PlayerList = self.raw.player_list[SEASON(self.raw.cur_year)]

        if appunti:
            self._add_notes(appunti)

        self.columns = ['Fascia', 'Budget', 'Ruolo', 'Giocatore', 'Squadra', 'QA', 'QI', 'QF', 'FVM', 'MV', 'Over6', 'Over6.5', 'MFV', 'BonusRate', 'Gol', 'Assist', 'WinRate', 'Presenze', 'Label', 'Notes']
        self.stats: dict[int: pd.DataFrame] = {}
        self.get_stats()

    def filters(self):
        return (
            [{'label': team, 'value': team} for team in self.stats['Squadra'].unique()],
            [{'label': role, 'value': role} for role in self.stats['Ruolo'].unique()],
            min([min(pd) for pd in self.stats['QA']]), max([max(pd) for pd in self.stats['QA']]),
            self.stats['FVM'].min(), self.stats['FVM'].max(),
            self.stats['MV'].min(), self.stats['MV'].max(),
            self.stats['MFV'].min(), self.stats['MFV'].max()
        )

    def _add_notes(self, appunticsv):
        appunti = pd.DataFrame(columns='Giocatore,Squadra,Ruolo,Q,FVM,Fascia,Budget,Label,Note'.split(','))
        appunti['Giocatore'] = [p.title() for p in self.cur_db.map.keys()]
        appunti['Squadra'] = [self.cur_db[p].team for p in self.cur_db.map.keys()]
        appunti['Ruolo'] = [self.cur_db[p].role for p in self.cur_db.map.keys()]
        appunti['Q'] = [self.cur_db[p].quotc for p in self.cur_db.map.keys()]
        appunti['FVM'] = [self.cur_db[p].fvmc for p in self.cur_db.map.keys()]
        appunti['Fascia'] = ''
        appunti['Budget'] = None
        appunti['Label'] = ''
        appunti['Note'] = ''
        if os.path.isfile(appunticsv):
            old_appunti = pd.read_csv(appunticsv, sep=';').fillna('')
            _, cur_exist, exist = np.intersect1d(appunti['Giocatore'], old_appunti['Giocatore'], return_indices=True)
            appunti.loc[cur_exist, 'Fascia'] = old_appunti.loc[exist, 'Fascia'].values
            appunti.loc[cur_exist, 'Budget'] = old_appunti.loc[exist, 'Budget'].values
            appunti.loc[cur_exist,  'Label'] = old_appunti.loc[exist,  'Label'].values
            appunti.loc[cur_exist,   'Note'] = old_appunti.loc[exist,   'Note'].values
            self.notes = appunti.copy()
            if not self.dryrun:
                appunti.fillna('', inplace=True)
                appunti.to_csv(appunticsv, sep=";", index=False, encoding='utf-8-sig')

    def get_stats(self, days="cur"):
        if days in self.stats.keys() and self.stats[days] is not None:
            pass
        else:
            self._add_stats(days=days)
            self.dump(dayslist=days)
        return self.stats[days]

    def _add_stats(self, days="cur"):
        y0 = 0
        if days == "cur":
            y0 = 0
        if days == "prec":
            y0 = 1
        print("Analysis of season", SEASON(self.raw.cur_year - y0))
        db = self.raw.player_list[SEASON(self.raw.cur_year - y0)]
        if days != "prec" and days != "cur":
            days = int(days)

        days_key = str(days)
        self.stats[days_key] = pd.DataFrame(columns=self.columns)

        old_players = list(db.map.keys())
        for p,i in self.cur_db.map.items():
            cur_player: Player = self.cur_db[p]
            row = self.notes.query(f'Giocatore == "{p.title()}"').iloc[0, :]
            fascia = row['Fascia']
            budget = row['Budget']
            if budget:
                budget = str(float(budget)*ASTA_BUDGET/100)
            note = row['Note']
            label = row['Label']
            if p in old_players and db[p].db is not None:
                player: Player = db[p]
                dbp = player.db
                if dbp.shape[0]:
                    days_count = dbp.shape[0]
                    dbp = player.db.query('Presenza != "Inutilizzato"')
                    if isinstance(days, int):
                        for y in range(y0 + 1, self.raw.years_to_analyse + 1):
                            if days_count >= days:
                                break
                            old_db = self.raw.player_list[SEASON(self.raw.cur_year - y)]
                            if p in old_db.map.keys() and old_db[p].db is not None:
                                tmp_db = old_db[p].db
                                if (days_count + tmp_db.shape[0]) >= days:
                                    days_count = days
                                    tmp_db = old_db[p].db.query('Presenza != "Inutilizzato"')
                                    dbp = pd.concat([tmp_db.iloc[-(days - days_count):, :], dbp])
                                else:
                                    days_count += tmp_db.shape[0]
                                    tmp_db = old_db[p].db.query('Presenza != "Inutilizzato"')
                                    dbp = pd.concat([tmp_db, dbp])

                    if dbp.shape[0]:
                        entry = [
                            fascia, budget, cur_player.role.upper(), p.title(), cur_player.team.title(), cur_player.quotc,
                            dbp['Quotazione'].iloc[0], dbp['Quotazione'].iloc[-1], cur_player.fvmc/1000*ASTA_BUDGET,
                            np.round(dbp['Voto'].mean(), 2), np.round(np.sum(dbp['Voto'] >= 6)/dbp.shape[0], 2),
                            np.round(np.sum(dbp['Voto'] >= 6.5)/dbp.shape[0], 2),
                            np.round(dbp['FantaVoto'].mean(), 2), np.round(dbp['Bonus'].mean(), 2),
                            dbp['Gol'].sum(), dbp['Assist'].sum(),
                            np.round(np.sum(dbp['GolFatti'] > dbp['GolSubiti'])/dbp.shape[0], 2),
                            dbp.shape[0], label, note
                        ]
                        self.stats[days_key].loc[len(self.stats[days_key].index), :] = entry
                    else:
                        entry = [
                            fascia, budget, cur_player.role.upper(), p.title(), cur_player.team.title(), cur_player.quotc,
                            None, None, cur_player.fvmc/1000*ASTA_BUDGET,
                            None, None, None,
                            None, None,
                            None, None,
                            None, 0, label, note
                        ]
                        self.stats[days_key].loc[len(self.stats[days_key].index), :] = entry
                else:
                    entry = [
                        fascia, budget, cur_player.role.upper(), p.title(), cur_player.team.title(), cur_player.quotc,
                        None, None, cur_player.fvmc/1000*ASTA_BUDGET,
                        None, None, None,
                        None, None,
                        None, None,
                        None, 0, label, note
                    ]
                    self.stats[days_key].loc[len(self.stats[days_key].index), :] = entry
            else:
                entry = [
                    fascia, budget, cur_player.role.upper(), p.title(), cur_player.team.title(), cur_player.quotc,
                    None, None, cur_player.fvmc/1000*ASTA_BUDGET,
                    None, None, None,
                    None, None,
                    None, None,
                    None, 0, label, note
                ]
                self.stats[days_key].loc[len(self.stats[days_key].index), :] = entry
            self.stats[days_key].sort_values(by=['Squadra', 'Budget'], ascending=[True, False])

    def dump(self, dayslist=None):
        if dayslist is None:
            dayslist = list(self.stats.keys())
        elif isinstance(dayslist, str) or isinstance(dayslist, int):
            dayslist = [dayslist]

        for days in dayslist:
            new_file = os.path.join(self.basepath, DATA_DIR, f'Stats_{days}.xlsx')
            writer = pd.ExcelWriter(new_file, engine='xlsxwriter', mode='w')
            workbook = writer.book
            bold = workbook.add_format({'bold': True})
            self.stats[days].to_excel(writer, sheet_name=f'Stats_{days}.xlsx', index=False)
            worksheet = writer.sheets[f'Stats_{days}.xlsx']

            def get_col_widths(dataframe, index=False):
                res = [max([len(str(s)) for s in dataframe[col].values] + [len(col)]) + 2 for col in dataframe.columns]
                idx_max = []
                if index:
                    idx_max = [max([len(str(s)) for s in dataframe.index.values] + [len(str(dataframe.index.name))]) + 2]
                return idx_max + res

            for i,width in enumerate(get_col_widths(self.stats[days])):
                worksheet.set_column(i, i, width)

            writer.close()

            # Conditional Formatting
            wb2 = spx.Workbook()
            wb2.LoadFromFile(new_file)
            def hex2rgba(h):
                from matplotlib.colors import to_rgba
                rgba = to_rgba(h)
                return [int(rgba[-1]*100)] + [int(v*255) for v in rgba[:-1]]

            # Quantiles
            # role_i = -1
            # unq_role = None
            # for i,c in enumerate(dfs[y].columns):
            #     if c == 'Ruolo':
            #         unq_role = dfs[y][c].unique()
            #         role_i = i
            #     if c in add_cols:
            #         excol = alfabeto[i]
            #         for r in unq_role:
            #             dfr = dfs[y][dfs[y]['Ruolo'] == r]
            #             filt_df = dfr[c].values[dfr[c].notna()]
            #             if len(filt_df) > 0:
            #                 qts = [np.quantile(filt_df, q) for q in quantiles]
            #                 qts += [1.0e+05]
            #                 cfs = destSheet.ConditionalFormats.Add()
            #                 cfs.AddRange(destSheet.Range["%s1:%s3000" % (excol, excol)])
            #                 for i in range(len(qts) - 1):
            #                     cf = cfs.AddCondition()
            #                     cf.FormatType = ConditionalFormatType.Formula
            #                     cf.FirstFormula = \
            #                         "AND(IF(%s1=\"%s\"; 1); IF(%s1>%g; 1); IF(%s1<%g; 1); IF(ISBLANK(%s1); 0; 1))" \
            #                         % (alfabeto[role_i], r, excol, qts[i], excol, qts[i + 1], excol)
            #                     cf.BackColor = Color.FromArgb(*hex2rgba(q_colors[-i]))
            # wb1.Dispose()

            # Teams
            for sheet in wb2.Worksheets:
                if sheet.LastRow > 0:
                    cfs = sheet.ConditionalFormats.Add()
                    cfs.AddRange(sheet.Range["A1:Z3000"])  #0, 0, sheet.LastRow, sheet.LastColumn])
                    for t,(cbg,cfg) in TEAM_COLORS.items():
                        cf = cfs.AddCondition()
                        cf.FormatType = spx.ConditionalFormatType.CellValue
                        cf.Operator = spx.ComparisonOperatorType.Equal
                        cf.FirstFormula = t
                        cf.BackColor = spxc.Color.FromArgb(*hex2rgba(cbg))
                        cf.FontColor = spxc.Color.FromArgb(*hex2rgba(cfg))

            # Save the result
            wb2.Save()
            wb2.Dispose()

            # writer = pd.ExcelWriter(new_file, engine='openpyxl', mode='a')
            # workbook = writer.book
            # workbook.remove(workbook['Evaluation Warning'])
            # writer.close()

            # os.system('mkdir tmp')
            # cmd = r'sed -i -e \'s/"AND(IF(\([A-Z][0-9]\)=""\([PDCA]\)"";/AND(IF(\1="\2";/g\' -e \'s/)"<\/formula>/)<\/formula>/g\' .\sheet8.xml .\sheet7.xml'




