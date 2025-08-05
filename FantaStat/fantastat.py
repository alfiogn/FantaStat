from driver import FANTASTAT_PATH, HOME, DATA_PATH
from scraper import SEASON

import os
import pandas as pd
import numpy as np


class FantaStat():
    def __init__(self, rawdata, xlsfile, sheet_name='Appunti'):
        self.raw = rawdata
        self.xls = xlsfile
        self.df_notes = pd.read_excel(self.xls, sheet_name=sheet_name).query("Fascia != 'D101'")
        self.df_stats = []

        self._add_stats()

    def _add_stats(self):
        new_cols = []
        last_valid = ''
        for c in self.df_notes.columns:
            if 'Unnamed' in c:
                new_cols.append(last_valid)
            else:
                new_cols.append(c)
                last_valid = c
        for i,c in enumerate(self.df_notes.iloc[0, :].values):
            if not pd.isna(c):
                new_cols[i] += '_' + c

        self.df_stats = []
        add_cols = ['Gol/H', 'Gol/PG', 'Gol/Sub', 'StdDev', 'Over6.5', 'VotoW/OGol']
        for y in range(self.raw.years_to_analyse + 1):
            print("Analysis of season", SEASON(self.raw.cur_year - y))
            df = self.df_notes.copy()
            df = df.iloc[1:]
            df.columns = new_cols

            for c in add_cols:
                df[c] = None
            for i,r in df.iterrows():
                n = r['Nome']
                p = self.raw[-y][n]

                if p is not None:
                    if p.voto is None:
                        continue
                    # spread:
                    # gol al minuto
                    # accuratezza gol: rapporto gol/presenza e gol/subentro (eg. pasalic)
                    # media voto buona anche se non fa bonus
                    # tanti bonus in generale
                    pres = p.db['Voto'].values > 0
                    if not any(pres):
                        continue
                    sub = p.db['Presenza'].values == 'Entrato'
                    df.loc[i, 'Gol/H'] = p.db['Gol'].sum()/p.db['Minuti'].sum()*60
                    df.loc[i, 'Gol/PG'] = p.db['Gol'][pres].sum()/np.sum(pres)
                    if np.sum(sub) > 0:
                        df.loc[i, 'Gol/Sub'] = p.db['Gol'][sub].sum()/np.sum(sub)

                    # control:
                    # media voto alta e costante (poca varianza)
                    # vedere top con voto >=6.5 (eg. barella)
                    # media su partite senza gol
                    # quantità di gol probabile sulla doppia bassa 10-15 (eg. morata)
                    # chi non ha coppe
                    df.loc[i, 'StdDev'] = np.std(p.db.query("Voto >= 0")['Voto'].values)
                    df.loc[i, 'Over6.5'] = np.sum(p.db['Voto'].values >= 6.25)/np.sum(pres)
                    df.loc[i, 'VotoW/OGol'] = np.average(p.db.query("Gol == 0").query("RF == 0")['Voto'].values)

            new_file = os.path.join(DATA_PATH, 'Stats%d.xlsx' % (self.raw.cur_year - y))
            writer = pd.ExcelWriter(new_file, engine='xlsxwriter', mode='w')
            df.to_excel(writer, sheet_name='Stats%d' % (self.raw.cur_year - y), index=False)
            writer.close()

            self.df_stats.append(df)

    # def dump(self, filename=self.xls):
    #     from spire.xls import *
    #     from spire.xls.common import *
    #     wb2 = Workbook()
    #     wb2.LoadFromFile(self.xls)
    #     def hex2rgba(h):
    #         from matplotlib.colors import to_rgba
    #         rgba = to_rgba(h)
    #         return [int(rgba[-1]*100)] + [int(v*255) for v in rgba[:-1]]

    #     alfabeto = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    #     q_colors = ['#FF69614D', '#AEC6CF4D', '#77DD774D']
    #     quantiles = [0.5, 0.75, 0.9]

    #     for y in range(N_YEARS + 1):
    #         # Initialize an instance of the Workbook class
    #         wb1 = Workbook()
    #         # Load an Excel workbook
    #         wb1.LoadFromFile(os.path.join(DATA_PATH, 'Stats%d.xlsx' % (raw.cur_year - y)))
    #         # Get the first worksheet
    #         sourceSheet = wb1.Worksheets[0]
    #         sheetName = sourceSheet.Name
    #         # Add a new worksheet with a specific name to the wb1
    #         destSheet = wb2.Worksheets.Add(sheetName)
    #         # Copy the first worksheet to the newly added worksheet
    #         destSheet.CopyFrom(sourceSheet)

    #         # role_i = -1
    #         # unq_role = None
    #         # for i,c in enumerate(dfs[y].columns):
    #         #     if c == 'Ruolo':
    #         #         unq_role = dfs[y][c].unique()
    #         #         role_i = i
    #         #     if c in add_cols:
    #         #         excol = alfabeto[i]
    #         #         for r in unq_role:
    #         #             dfr = dfs[y][dfs[y]['Ruolo'] == r]
    #         #             filt_df = dfr[c].values[dfr[c].notna()]
    #         #             if len(filt_df) > 0:
    #         #                 qts = [np.quantile(filt_df, q) for q in quantiles]
    #         #                 qts += [1.0e+05]
    #         #                 cfs = destSheet.ConditionalFormats.Add()
    #         #                 cfs.AddRange(destSheet.Range["%s1:%s3000" % (excol, excol)])
    #         #                 for i in range(len(qts) - 1):
    #         #                     cf = cfs.AddCondition()
    #         #                     cf.FormatType = ConditionalFormatType.Formula
    #         #                     cf.FirstFormula = \
    #         #                         "AND(IF(%s1=\"%s\"; 1); IF(%s1>%g; 1); IF(%s1<%g; 1); IF(ISBLANK(%s1); 0; 1))" \
    #         #                         % (alfabeto[role_i], r, excol, qts[i], excol, qts[i + 1], excol)
    #         #                     cf.BackColor = Color.FromArgb(*hex2rgba(q_colors[-i]))

    #         wb1.Dispose()


    #     # Conditional Formatting Teams
    #     for sheet in wb2.Worksheets:
    #         if sheet.LastRow > 0:
    #             cfs = sheet.ConditionalFormats.Add()
    #             cfs.AddRange(sheet.Range["A1:Z3000"])  #0, 0, sheet.LastRow, sheet.LastColumn])
    #             for t,(cbg,cfg) in TEAM_COLORS.items():
    #                 cf = cfs.AddCondition()
    #                 cf.FormatType = ConditionalFormatType.CellValue
    #                 cf.Operator = ComparisonOperatorType.Equal
    #                 cf.FirstFormula = t
    #                 cf.BackColor = Color.FromArgb(*hex2rgba(cbg))
    #                 cf.FontColor = Color.FromArgb(*hex2rgba(cfg))

    #     # Save the result
    #     wb2.Save()
    #     wb2.Dispose()

    #     # os.system('mkdir tmp')
    #     # cmd = r'sed -i -e \'s/"AND(IF(\([A-Z][0-9]\)=""\([PDCA]\)"";/AND(IF(\1="\2";/g\' -e \'s/)"<\/formula>/)<\/formula>/g\' .\sheet8.xml .\sheet7.xml'




