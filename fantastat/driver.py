from selenium.webdriver import Firefox
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

import os, glob, pickle, time, pdb

from . import utils

FANTASTAT_PATH = os.path.dirname(os.path.abspath(__file__))
HOME = os.getenv('HOME')

class driver(Firefox):
    def __init__(self, profile=False, load_cookies=False, headless=True):
        profile_path, exe, self.user, self.password = utils.Setup()
        self.login_done = False
        options = Options()
        options._profile = None
        self.download_path = './data'
        if not os.path.exists(self.download_path):
            os.mkdir(self.download_path)
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", self.download_path)
        if profile:
            options._profile = FirefoxProfile(profile_path)
        if headless:
            options.headless = True
        self.options = options
        log_path = '/'.join([FANTASTAT_PATH, 'geckodriver.log'])
        service = Service(exe, log_path=log_path)
        super().__init__(service=service, options=options)

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
        try:
            self.WaitClick("//button[contains(., 'ACCETTO')]")
        except:
            time.sleep(0.1)
            print("Warning! No cookies found 0")
        try:
            self.WaitClick("//button[contains(., 'No, voglio perdere!')]")
        except:
            time.sleep(0.1)
            print("Warning! No cookies found 1")

    def FantaLogin(self, url='https://www.fantacalcio.it/'):
        self.get(url)
        print("Login to fantacalcio.it", end=" --> ")
        self.CookiesAccept()
        # find user button
        self.WaitClick("/html/body/main/header/nav[1]/ul/li[8]/button")
        # go to login page
        self.WaitClick("//a[@href='/login']")

        # perform login
        username = self.find_element(By.XPATH, "//input[@name='username']")
        password = self.find_element(By.XPATH, "//input[@name='password']")
        username.send_keys(self.user)
        password.send_keys(self.password)
        self.WaitClick("//button[contains(., 'Login')]", t=0)
        self.login_done = True

    def StoreDownload(self, file, filename=None):
        if filename is None:
            os.rename(file, '/'.join([self.download_path, file.split('/')[-1]]))
        else:
            os.rename(file, '/'.join([self.download_path, filename]))

    def CheckData(self, file):
        return os.path.isfile('/'.join([self.download_path, file]))

    def CheckTimeStamp(self, file, days=1):
        # return yes if time stamp is more than `days`
        filetime = os.path.getmtime('/'.join([self.download_path, file]))
        return ((time.time() - filetime) / 3600 > 24*days)

    def Download(self, url, prefix=None):
        self.Get(url)
        self.Click("//a[contains(@href, 'Excel')]")
        fileext = "part"
        latest_file = ""
        while "part" == fileext:
            time.sleep(0.1)
            files = glob.glob('/'.join([HOME, 'Downloads', '*.*']))
            if len(files) > 0:
                latest_file = max(files, key=os.path.getmtime)
                ext = latest_file.split('/')[-1].split('.')[-1]
                fileext = ext

        self.StoreDownload(latest_file, filename='.'.join([prefix, ext]))



