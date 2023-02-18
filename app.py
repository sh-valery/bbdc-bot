import random
from time import sleep

import requests
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bot import send_message
import logging
import json

# setup logging
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

known_days = {}
known_sessions = {}


class BBDCProcessor:
    def __init__(self, config):
        logging.info("parse config")

        self._username = config["bbdc"]["username"]
        self._password = config["bbdc"]["password"]

        # bot
        self._bot_token = config["telegram"]["token"]
        self._chat_id = config["telegram"]["chat_id"]

        # connect to chrome
        logging.info("connect to selenium")
        chrome_host = config["chromedriver"]["host"]
        self.browser = webdriver.Remote(
            '{:}/wd/hub'.format(chrome_host), DesiredCapabilities.CHROME)

    def run(self):
        logging.info("parse and notify")
        try:
            self.browser.get('https://booking.bbdc.sg/#/login?redirect=%2Fbooking%2Findex')
            self._login()
            self._open_practical_tab()

            header = self._get_lesson_name()
            logging.info(f"choose lesson: {header}")

            days = self._get_new_available_days()
            logging.info(f"New days found: {days}")
            if len(days) > 0:
                send_message(self._bot_token, self._chat_id, f"{header} \n New days found: {days}")

            # Wait for new available slots to be loaded
            slots = self._get_new_available_slots()
            logging.info(f"New slots found: {slots}")
            if len(slots) > 0:
                send_message(self._bot_token, self._chat_id, f"{header} \n New slots found:\n{''.join(slots)}")

            # parse calendar
            while True:
                logging.info("parsing calendar...")
                self._parse_and_notify()
                logging.info("wait for 30-150 seconds before refresh...")
                sleep(random.randint(30, 150))
                logging.info("refreshing...")
                self.browser.refresh()

        except Exception as e:
            logging.exception(e)
            send_message(self._bot_token, self._chat_id, f"[Error]\n{e}")
            raise
        finally:
            self.browser.quit()

    def _login(self):
        logging.info("login")

        # Wait for the login form to be loaded
        wait = WebDriverWait(self.browser, 10)
        idLogin = wait.until(EC.presence_of_element_located((By.ID, 'input-8')))
        idLogin.send_keys(self._username)
        idPassword = wait.until(EC.presence_of_element_located((By.ID, 'input-15')))
        idPassword.send_keys(self._password)

        # Wait for the login button to be clickable
        loginButton = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'v-btn')))
        loginButton.click()
        self.browser.switch_to.default_content()

    def _open_practical_tab(self):
        wait = WebDriverWait(self.browser, 10)
        practical = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//*[@id="app"]/div/div/main/div/div/div[2]/div/div[1]/div/div/div[1]/div/div[2]/div/div[2]')))
        logging.info("click practical button")
        practical.click()

    def _parse_and_notify(self):
        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.XPATH,
                                                   '//button[@class="v-btn v-btn--is-elevated v-btn--has-bg theme--light v-size--default primary"]')))
        logging.info("click booking button")
        book_next = self.browser.find_elements_by_xpath(
            '//button[@class="v-btn v-btn--is-elevated v-btn--has-bg theme--light v-size--default primary"]')[-1]

        book_next.click()

        # if have booked lesson, click continue
        try:
            continue_button = self.browser.find_element_by_xpath(
                '/html/body/div[1]/div[3]/div/div/div[2]/button[2]')
            continue_button.click()
        except NoSuchElementException:
            logging.info("No continue button")

    def _get_new_available_slots(self):
        wait = WebDriverWait(self.browser, 10)

        wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "available-slot__item__time")]')))

        browser = self.browser
        sessions = browser.find_elements_by_class_name('sessionList')
        new_known_sessions = {}
        sessions_to_notify = []
        for s in sessions:
            if s.text == '':  # skip empty blocks
                continue

            date, total, name, time, cost = s.text.splitlines()
            logging.info(f"Session found: {date} {time}")
            if f'{date} {time}' not in known_sessions:
                known_sessions[f'{date} {time}'] = True
                logging.warning(f"[NEW] New session found: {date} {time}")
                sessions_to_notify.append(f"{date} {time}\n")
            new_known_sessions[f'{date} {time}'] = True

        # refresh known sessions
        known_sessions.clear()
        known_sessions.update(new_known_sessions)
        return sessions_to_notify

    def _get_new_available_days(self):
        wait = WebDriverWait(self.browser, 10)

        wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "available-day__day__date")]')))

        browser = self.browser
        calendar = browser.find_element_by_xpath(
            '/html/body/div[1]/div/div/main/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]/div[4]/div/div/div')

        days_to_notify = []
        new_known_days = {}
        for day in calendar.find_elements_by_class_name('v-btn__content'):
            logging.info(f"Day found: {day.text}")
            new_known_days[day.text] = True
            if day.text not in known_days:
                days_to_notify.append(day.text)
                logging.warning(f"[NEW] New day found: {day.text}")
            day.click()
            sleep(random.randint(2, 4))

        # refresh known days
        known_days.clear()
        known_days.update(new_known_days)
        return days_to_notify

    def _get_lesson_name(self) -> str:
        try:
            self.browser.find_element_by_xpath('//p[@class="title d-block d-md-none"]')
            return self.browser.find_element_by_xpath('//p[@class="title d-block d-md-none"]').text
        except NoSuchElementException:
            logging.info("No header for the lesson")
            return "Unknow lesson name"

