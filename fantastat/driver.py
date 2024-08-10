from selenium.webdriver import Firefox
from selenium.webdriver.firefox.service import Service as FireService
from selenium.webdriver.firefox.options import Options as FireOptions

from selenium.webdriver import Safari
from selenium.webdriver.safari.service import Service as SafariService
from selenium.webdriver.safari.options import Options as SafariOptions

from selenium.webdriver.edge.service import Service as EdgeService

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

import os, glob, pickle, time, pdb

from . import utils
from .utils import sys_browser

FANTASTAT_PATH = os.path.dirname(os.path.abspath(__file__))
HOME = os.getenv('HOME')
if HOME is None:
    HOME = os.getenv('HOMEPATH')

class driver(webdriver.Safari):
    def __init__(self, load_cookies=False, headless=True):
        exe, self.user, self.password = utils.Setup()
        self.login_done = False
        options = None
        self.download_path = './data'
        if not os.path.exists(self.download_path):
            os.mkdir(self.download_path)
        if sys_browser == 'firefox':
            options = FireOptions()
            options._profile = None
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", self.download_path)
            if headless:
                options.headless = True
        elif sys_browser == 'safari':
            options = SafariOptions()
            options._profile = None
            # options.set_preference("browser.download.folderList", 2)
            # options.set_preference("browser.download.dir", self.download_path)
            if headless:
                options.headless = True
        elif sys_browser == 'edge':
            # C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
            data_fld = "C:\\Users\\" + os.getenv("HOSTNAME") + "\\AppData\\Local\\Microsoft\\Edge\\Profile1"
            options = webdriver.EdgeOptions()
            options.use_chromium = True
            options.add_argument('log-level=3')
            # options.add_argument('--disable-gpu')
            # options.add_argument('--profile-directory=User Data1')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--user-data-dir=' + data_fld)
            options.add_experimental_option('prefs', {
                        'download.default_directory': self.download_path,
                        'download.prompt_for_download': False,
                        'download.directory_upgrade': True,
                        'safebrowsing.enabled': True,
                        'profile.default_content_settings.popups': False,
                        'download.default_content_setting_values.automatic_downloads': 1,
            })
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            if headless:
                options.add_argument("--headless")
        self.options = options
        service = None
        if sys_browser == 'firefox':
            service = FireService(exe)
            super().__init__(service=service, options=self.options)
        elif sys_browser == 'safari':
            service = SafariService(exe)
            super().__init__(service=service, options=self.options)
        elif sys_browser == 'edge':
            service = EdgeService(exe)
            super().__init__(service=service, options=self.options, keep_alive=True)
        # super().manage().timeouts().implicitlyWait(10, TimeUnit.SECONDS);

    def Get(self, url):
        if not self.login_done:
            self.FantaLogin()
        self.get(url)

    def WaitClick(self, xpath, t=8):
        WebDriverWait(self, t).until(
            expected_conditions.element_to_be_clickable(
                (By.XPATH, xpath)
            )
        ).click()

    def Click(self, xpath):
        els = self.find_elements(By.XPATH, xpath)
        if len(els) > 0:
            els[0].click()

    def CookiesAccept(self):
        time.sleep(1)
        try:
            self.WaitClick("//button[contains(., 'ACCETTO')]")
        except:
            time.sleep(0.1)
            print("Warning! No cookies found 0")
        try:
            self.WaitClick('//*[@id="pushengage-opt-in-6-close"]', t=2)
        except:
            time.sleep(0.1)
            print("Warning! No cookies found 1")

    def FantaLogin(self, url='https://www.fantacalcio.it/'):
        self.get(url)
        # self.maximize_window()
        print("Login to fantacalcio.it", end=" --> ")
        self.CookiesAccept()
        # find user button
        self.WaitClick('//*[@id="main-header"]/nav[1]/ul/li[8]/button')
        # go to login page
        xp = "//a[@href='/login']"
        els = self.find_elements(By.XPATH, xp)
        if len(els) > 0:
            if els[0].text != '':
                self.WaitClick(xp)
                time.sleep(1)
                # perform login
                username = self.find_element(By.XPATH, '//*[@id="loginForm"]/div[1]/input')
                password = self.find_element(By.XPATH, '//*[@id="loginForm"]/div[2]/input')
                username.send_keys(self.user)
                password.send_keys(self.password)
                self.WaitClick('//*[@id="loginForm"]/button', t=0.1)
                time.sleep(1)

        self.login_done = True

    def StoreDownload(self, file, filename=None):
        if filename is None:
            filename = file.split('/')[-1]

        filename = '/'.join([self.download_path, filename])
        if os.path.isfile(filename):
            os.remove(filename)
        os.rename(file, filename)

    def CheckData(self, file):
        return os.path.isfile('/'.join([self.download_path, file]))

    def CheckTimeStamp(self, file, days=1):
        if self.CheckData(file):
            # return yes if time stamp is more than `days`
            filetime = os.path.getmtime('/'.join([self.download_path, file]))
            return ((time.time() - filetime) / 3600 > 24*days)
        else:
            return False

    def Download(self, url, prefix=None):
        # try:
        dl_ext = ["crdownload", "download"]
        self.Get(url)
        self.Click("//a[contains(@href, 'Excel')]")
        fileext = ""
        latest_file = ""
        seconds = 0
        exts = []
        while seconds < 10:
            time.sleep(0.1)
            files = glob.glob('/'.join([HOME, 'Downloads', '*.*']))
            if len(files) > 0:
                latest_file = max(files, key=os.path.getmtime)
                exts = latest_file.split('/')[-1].split('.')
                fileext = exts[-1]
            if 'xls' in fileext:
                seconds = 20
            seconds += 0.1
        time.sleep(1)

        if any([e in fileext  for e in dl_ext]):
            for e in dl_ext:
                if os.path.isfile(latest_file) and '.' + e in latest_file:
                    os.rename(latest_file, latest_file.replace('.' + e, ''))
                    latest_file = latest_file.replace('.' + e, '')
        ext = latest_file.split('/')[-1].split('.')[-1]
        try:
            self.StoreDownload(latest_file, filename='.'.join([prefix, ext]))
        except:
            RuntimeError("Something wrong with url = ", url, "\n", latest_file, "into '", prefix, ext, "'")
        # except:
        #     print("Manual download required for ", url)




