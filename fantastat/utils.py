import os, sys, re, pdb
import matplotlib.pyplot as plt
import plotly.offline
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication
from selenium.webdriver.common.by import By
from .championship import CURRENT_YEAR

sys_browser = 'firefox'
if os.name == 'nt':
    sys_browser = 'edge'

quot_prefix = lambda i: 'quotazioni' + '20' + str(i)
stat_prefix = lambda i: 'statistiche' + '20' + str(i)
voti_prefix = lambda i,j: 'voti' + '20' + str(i) + '_' + str(j)

def CreatePlot():
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.grid(True)
    return fig, ax

def ShowFig(fig, name):
    plotly.offline.plot(fig, filename=name+'.html', auto_open=False)
    app = QApplication(sys.argv)
    web = QWebEngineView()
    web.load(QUrl.fromLocalFile(name+'.html'))
    web.show()
    sys.exit(app.exec_())

def Setup():
    home = os.getenv('HOME')
    if home is None:
        home = os.getenv('HOMEPATH')
    # pwd = os.path.dirname(os.path.abspath(__file__))
    pwd = os.getcwd()
    print("\nWorking directory to", pwd)
    os.chdir(pwd)
    exe_browser = None
    if sys_browser == 'firefox':
        exe_browser = '/'.join([pwd, 'fantastat/geckodriver'])
        exe_browser = '/'.join([pwd, 'fantastat\geckodriver.exe'])
    elif sys_browser == 'edge':
        exe_browser = '\\'.join([pwd, 'fantastat\msedgedriver.exe'])

    user = os.environ['USER']
    password = os.environ['PASSWORD']

    return exe_browser, user, password

def DownloadXLSX(b, q, s, v, update=False):
    ext = '.xlsx'
    for i in range(15, 24):
        forceUpdate = i == CURRENT_YEAR and update
        if not b.CheckData(quot_prefix(i) + str(ext)) \
           or (i == CURRENT_YEAR and b.CheckTimeStamp(quot_prefix(i) + str(ext), days=5)) \
           or forceUpdate:
            print("Download quotazioni", i)
            b.Download(q(i), prefix='quotazioni' + '20' + str(i))
        if not b.CheckData(stat_prefix(i) + str(ext)) \
           or (i == CURRENT_YEAR and b.CheckTimeStamp(stat_prefix(i) + str(ext), days=5)) \
           or forceUpdate:
            print("Download statistiche", i)
            b.Download(s(i), prefix=stat_prefix(i))
        for j in range(1, 39):
            end = False
            if i == CURRENT_YEAR:
                b.get(v(i, j))
                avail = \
                    b.find_elements(
                        By.XPATH,
                        '//div[contains(., "Voti non disponibili")]'
                    )
                if len(avail) > 0:
                    end = True
            if end:
                break
            else:
                if not b.CheckData(voti_prefix(i, j) + str(ext)) or forceUpdate:
                    print("Download voti", i, j)
                    b.Download(v(i, j), prefix=voti_prefix(i, j))


