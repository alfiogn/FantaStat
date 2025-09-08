import argparse
from argparse import ArgumentParser, REMAINDER

import os
import re
import shutil
import glob

import FantaStat as fs
from FantaStat.player import Player, PlayerList
from FantaStat.scraper import Scraper, LIST_NAME, SEASON, PLAYER_LIST_NAME
from FantaStat.fantastat import FantaStat as stats
from FantaStat.dashboard.dashboard import Dashboard
from FantaStat.driver import Driver, DATA_DIR


def get_args_parser() -> ArgumentParser:
    """Parse the command line options."""
    parser = ArgumentParser(
        description="Use FantaStat Toolkit",
        formatter_class=argparse.RawTextHelpFormatter
    )

    #
    # Optional arguments.
    #

    parser.add_argument(
        "--update",
        dest="update",
        action='store_true',
        help='Update data.'
    )

    parser.add_argument(
        "--update-db",
        dest="updatedb",
        action='store_true',
        help='Update players list. Often due to FantaStat library variations.'
    )

    parser.add_argument(
        "--force",
        dest="force",
        action='store_true',
        help='Force players list update.'
    )

    parser.add_argument(
        "--dry-run",
        dest="dryrun",
        action='store_true',
        help='Do not save any new file.'
    )

    parser.add_argument(
        "--verbose", "-v",
        dest="verbose",
        action='store_true',
        help='Verbose mode.'
    )

    parser.add_argument(
        '--n-years',
        dest='nyears',
        type=int,
        default=1,
        help='Consider current year - <nyears>. Default: 1.'
    )

    parser.add_argument(
        '--dir',
        dest='directory',
        type=str,
        default='.',
        help='Start from specified directory. Default: ".".'
    )

    parser.add_argument(
        '--dashboard',
        dest='dashboard',
        action='store_true',
        help='Start the FantaStat dashboard.'
    )

    parser.add_argument(
        '--dashboard-help',
        dest='dashboardhelp',
        action='store_true',
        help='Get help for the FantaStat dashboard creation.'
    )

    parser.add_argument(
        '--rebuild',
        dest='dashboardrebuild',
        action='store_true',
        help='Start the FantaStat dashboard with rebuild.'
    )

    parser.add_argument(
        '--player-notes',
        dest='playernotes',
        type=str,
        help="CSV UTF-8 file with the form\n"
        "Giocatore ; Fascia ;  Budget ; Label ;  Note\n"
        "    <str> ;  <str> ; <float> ; <str> ; <str>\n\n"
        "  - Giocatore: name of the player (str.title)\n"
        "  -    Fascia: TOP > SEMI > F3 > F4 > SCO > F5 > None\n"
        "  -    Budget: suggested %% of the total budget cap\n"
        "  -     Label: Bug|Mod|Low|Bon|Hype\n"
        "  -      Note: notes on the player"
    )

    parser.add_argument(
        '--notes',
        dest='notes',
        type=str,
        help="Markdown document with general notes."
    )

    parser.set_defaults(update=False)
    parser.set_defaults(updatedb=False)
    parser.set_defaults(dashboard=False)
    parser.set_defaults(playernotes=None)
    parser.set_defaults(notes=None)

    #
    # Positional arguments.
    #

    # parser.add_argument(
    #     "input_mode",
    #     type=str,
    #     help="Input mode:\n"
    #     "  - scrap: scrap data from the web\n"
    #     "  - dashboard: launch the FantaStat dashboard\n",
    # )

    # Rest from the training program.
    # parser.add_argument("other_args_list", nargs=REMAINDER)

    return parser


def parse_args(args):
    parser = get_args_parser()
    return parser.parse_args(args)


def run(args):
    """Run the tool."""
    print("CWD:", os.path.abspath(args.directory))
    if args.dashboardhelp:
        Dashboard().run(help=args.dashboardhelp)
        return

    data_path = os.path.join(args.directory, DATA_DIR)
    raw = Scraper(n_years=args.nyears, basepath=args.directory, verbose=args.verbose)

    if args.force and not args.dryrun:
        l = [
            int(re.search('z[0-9]*_', s).group().replace('z', '').replace('_', ''))
            for s in glob.glob(os.path.join(data_path, 'z*'))
        ]
        l.sort()
        n = l[-1]
        lname = LIST_NAME(SEASON(raw.cur_year))
        shutil.move(os.path.join(data_path, lname), os.path.join(data_path, 'z%d_' % (n + 1) + lname))
        fname = PLAYER_LIST_NAME(SEASON(raw.cur_year))
        shutil.move(os.path.join(data_path, fname), os.path.join(data_path, 'z%d_' % (n + 1) + fname))

    raw.ScrapAll(updatelist=args.update, updatedata=args.update, dryrun=args.dryrun)
    if args.updatedb:
        raw.UpdateAll(dryrun=args.dryrun)

    fs = stats(raw, appunti=args.playernotes, dryrun=args.dryrun)
    fs.dump()

    if args.dashboard:
    #     fanta_df = pd.read_excel('lista_calciatori_lista calciatori_classic_fantagheis-2024-2025.xlsx')
    #     fanta_df['name'] = fanta_df['Nome']
    #     fanta_df['fantateam'] = fanta_df['FantaSquadra']
    #     fanta_df.loc[fanta_df['FantaSquadra'].isna(), 'fantateam'] = 'Svincolato'
    #     fanta_df.loc[fanta_df['Fuori lista'] == '*', 'fantateam'] = 'Fuori lista'
        app = Dashboard(fs, appunti=args.notes)
        app.run(debug=args.verbose, rebuild=args.dashboardrebuild)


def main(args=None):
    args = parse_args(args)
    run(args)


if __name__ == "__main__":
    main()


