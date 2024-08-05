import os, sys, pickle
from fantastat.dashboard import dashboard
from fantastat.championship import CURRENT_YEAR
import pandas as pd
import numpy as np

import argparse

parser = argparse.ArgumentParser(description='Open FantaStat dashboard.')
parser.add_argument('--update', dest='update', action='store_true', help='trigger update of marks, results and priorities')
parser.add_argument('--db-to-csv', dest='tocsv', help='pandas (in pickle) database to be converted to csv')
parser.add_argument('--csv-to-db', dest='todb', help='csv to be converted into pandas (in pickle)')
parser.add_argument('--last-to-load', dest='lastdays', help='last days to load')
parser.set_defaults(update=False)
parser.set_defaults(lastdays='20')

args = parser.parse_args()

if (args.tocsv is not None) ^ (args.todb is not None):
    if args.tocsv is not None:
        file = open(args.tocsv, 'rb')
        if args.tocsv[-7:] != '.pickle':
            raise RuntimeError("Extension of %s not .pickle" % args.tocsv)
        os.system('cp %s %s_backup' % (args.tocsv, args.tocsv))
        db = pd.read_pickle(file)
        newfile = args.tocsv[:-7] + '.csv'
        db.to_csv(newfile, index=False)
    else:
        if args.todb[-4:] != '.csv':
            raise RuntimeError("Extension of %s not .csv" % args.todb)
        newfile = args.todb[:-4] + '.pickle'
        db = pd.read_csv(args.todb)
        pickle.dump(db, open(newfile, 'wb'))


#### Infografiche
# probabili_formazioni_2324 = 'https://www.fantacalcio.it/news/calcio-italia/05_08_2023/calciomercato-come-cambia-la-serie-a-2023-24-le-probabili-formazioni-446506'
# probabili_formazioni_2324 = 'https://www.fantacalcio.it/news/calcio-italia/01_02_2024/calciomercato-serie-a-probabili-formazioni-455658'
probabili_formazioni_2425 = 'https://www.fantacalcio.it/news/01_08_2024/asta-fantacalcio-le-probabili-formazioni-della-serie-a-2024-25-464086'
rigoristi = 'https://www.fantacalcio.it/rigoristi-serie-a'
probabili_formazioni = 'https://www.fantacalcio.it/probabili-formazioni-serie-a'

voti = lambda y,n: 'https://www.fantacalcio.it/voti-fantacalcio-serie-a/20'+str(y)+'-'+str(y+1)+'/'+str(n)
statistiche = lambda y: 'https://www.fantacalcio.it/statistiche-serie-a/20'+str(y)+'-'+str(y+1)+'/statistico/riepilogo'
quotazioni = lambda y: 'https://www.fantacalcio.it/quotazioni-fantacalcio/20'+str(y)
seriea = 'https://www.legaseriea.it/it/serie-a'

db = dashboard(15, CURRENT_YEAR - 1, quotazioni, statistiche, voti, seriea,
               prob=probabili_formazioni, rig=rigoristi, last=int(args.lastdays),
               approb=probabili_formazioni_2425, update=args.update, headless=False)
# NOTE: Set headless=False to see what Firefox does

if __name__ == '__main__':
    # db.run_server(debug=True, run=False)
    # db.run_server(debug=True)
    db.run_server()





