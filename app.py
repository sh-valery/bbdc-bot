import os
import random
from datetime import datetime, timedelta
from time import sleep
from typing import List

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bot import send_message
import logging

# setup logging
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


class BBDCProcessor:
    def __init__(self, config):
        logging.info("parse config...")

        self._username = config["bbdc"]["username"]
        self._password = config["bbdc"]["password"]

        # bot
        self._bot_token = config["telegram"]["token"]
        self._chat_id = config["telegram"]["chat_id"]

        # connect to chrome
        logging.info("connect to selenium")
        chrome_host = config["chromedriver"]["host"]

        logging.info(f"connecting to selenium host: {chrome_host}")
        self.browser = webdriver.Remote(
            '{:}/wd/hub'.format(chrome_host), DesiredCapabilities.CHROME)

        self._last_time_report = None
        self.known_days = {}
        self.known_sessions = {}

    def run(self):
        try:
            logging.info("login...")
            self._login()

            logging.info(f"open practical tab...")
            self._open_practical_tab()

            logging.info(f"open slots...")
            self._open_slots()

        except Exception as e:
            logging.exception(e)
            send_message(self._bot_token, self._chat_id, f"[Error]\n{str(e)}")
            os.exit(1)

            # parse calendar every 30-150 seconds and send message if new slots are available
            while True:
                try:
                    # report with new days
                    logging.info("parsing calendar...")
                    days = self._get_new_available_days()
                    logging.info(f"New days found: {days}")

                    header = self._get_lesson_name()
                    logging.info(f"choose lesson: {header}")

                    if len(days) > 0:
                        send_message(self._bot_token, self._chat_id, f"{header} \n New days found: {days}")

                    # detailed report with new slots
                    slots = self._get_new_available_slots()
                    logging.info(f"New slots found: {slots}")
                    if len(slots) > 0:
                        send_message(self._bot_token, self._chat_id, f"{header} \n New slots found:\n{''.join(slots)}")
                        self._last_time_report = datetime.now()

                    if len(days) == 0 and len(slots) == 0:
                        logging.info("no new slots found")

                    if datetime.now() > self._last_time_report + timedelta(minutes=30):
                        logging.info("no new slots found for 30 minutes, send health report...")
                        send_message(self._bot_token, self._chat_id, f"[Health report]\n{header} \n no new slots found for 30 minutes")

                    logging.info("wait for 30-150 seconds before refresh...")
                    sleep(random.randint(30, 150))
                    logging.info("refreshing...")
                    self.browser.refresh()

                except Exception as e:
                    logging.exception(e)
                    send_message(self._bot_token, self._chat_id, f"[Error]\n{str(e)}\nrefresh and sleep 60 seconds...")
                    self.browser.refresh()
                    sleep(60)
    def _login(self):
        self.browser.get('https://booking.bbdc.sg/#/login?redirect=%2Fbooking%2Findex')

        # Wait for the login form to be loaded
        wait = WebDriverWait(self.browser, 10)
        id_login = wait.until(EC.presence_of_element_located((By.ID, 'input-8')))
        id_login.send_keys(self._username)
        id_password = wait.until(EC.presence_of_element_located((By.ID, 'input-15')))
        id_password.send_keys(self._password)

        # Wait for the login button to be clickable
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'v-btn')))
        login_button.click()
        self.browser.switch_to.default_content()

    def _open_practical_tab(self):
        logging.info("waiting practical button to be clickable")
        sleep(30)
        wait = WebDriverWait(self.browser, 30)
        practical = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//*[@id="app"]/div/div/main/div/div/div[2]/div/div[1]/div/div/div[1]/div/div[2]/div/div[2]')))
        logging.info("click practical button")
        practical.click()

    def _open_slots(self):
        logging.info("waiting booking button to be clickable")
        sleep(30)
        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.XPATH,
                                                   '//button[@class="v-btn v-btn--is-elevated v-btn--has-bg theme--light v-size--default primary"]')))
        logging.info("click booking button")
        book_next = self.browser.find_elements(By.XPATH,
                                               '//button[@class="v-btn v-btn--is-elevated v-btn--has-bg theme--light v-size--default primary"]')[
            -1]
        book_next.click()

        # if have booked lesson, click continue
        try:
            continue_button = self.browser.find_element(By.XPATH,
                                                        '/html/body/div[1]/div[3]/div/div/div[2]/button[2]')
            continue_button.click()
        except NoSuchElementException:
            logging.info("No continue button")

    def _get_new_available_slots(self) -> List[str]:
        wait = WebDriverWait(self.browser, 60)
        wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'sessionList')))
        sessions = self.browser.find_elements(By.CLASS_NAME, 'sessionList')
        new_known_sessions = {}
        sessions_to_notify = []
        for s in sessions:
            if s.text == '':  # skip empty blocks
                continue
            date = s.text.splitlines()[0]
            for card in s.find_elements(By.CLASS_NAME, 'sessionCard'):
                if card.text == '':
                    continue

                name, time, cost = card.text.splitlines()
                logging.info(f"Session found: {date} {time}")
                if f'{date} {time}' not in self.known_sessions:
                    self.known_sessions[f'{date} {time}'] = True
                    logging.warning(f"[NEW] New session found: {date} {time}")
                    sessions_to_notify.append(f"{date} {time}\n")
                new_known_sessions[f'{date} {time}'] = True

        # refresh known sessions
        self.known_sessions.clear()
        self.known_sessions.update(new_known_sessions)
        return sessions_to_notify

    def _get_new_available_days(self) -> List[str]:
        wait = WebDriverWait(self.browser, 10)
        calendar = wait.until(
            EC.presence_of_element_located((By.XPATH,
                                            '/html/body/div[1]/div/div/main/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]/div[4]/div/div/div')))
        days_to_notify = []
        new_known_days = {}
        for day in calendar.find_elements(By.CLASS_NAME, 'v-btn__content'):
            logging.info(f"Day found: {day.text}")
            new_known_days[day.text] = True
            if day.text not in self.known_days:
                days_to_notify.append(day.text)
                logging.warning(f"[NEW] New day found: {day.text}")
            day.click()
            sleep(random.randint(2, 4))
        # refresh known days
        self.known_days.clear()
        self.known_days.update(new_known_days)
        return days_to_notify

    def _get_lesson_name(self) -> str:
        try:
            lesson_title = self.browser.find_element(By.XPATH, '//p[@class="title title-blue d-none d-md-block"]')
            lesson_title = lesson_title.text
            if lesson_title == "":
                logging.warning("No header for the lesson")
            return lesson_title

        except NoSuchElementException:
            logging.info("No header for the lesson")
            return "Unknow lesson name"
