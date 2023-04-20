import json
import logging
import random
from datetime import datetime, timedelta, timezone, time
from time import sleep
from typing import List

import requests
from selenium import webdriver
from selenium.common import TimeoutException, InvalidSessionIdException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bot import send_message
from lesson_map import practical_lessons, theoretical_lessons, test_lessons
from model import Slot

# setup logging
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


class BBDCProcessor:
    def __init__(self, config):
        logging.info("parse config...")

        self._username = config["bbdc"]["username"]
        self._password = config["bbdc"]["password"]
        self._auto_booking = config["bbdc"].get('auto_book', False)

        # bot
        self._bot_token = config["telegram"]["token"]
        self._chat_id = config["telegram"]["chat_id"]

        # connect to chrome
        logging.info("connect to selenium")
        chrome_host = config["chromedriver"]["host"]

        logging.info(f"connecting to selenium host: {chrome_host}")
        bbdc = config["bbdc"]
        self._practical_lesson_target = bbdc.get("practical_lesson_target")
        self._theory_lesson_target = bbdc.get("theory_lesson_target")
        self._test_target = bbdc.get("test_target")
        # todo
        self.browser = webdriver.Remote(
            '{:}/wd/hub'.format(chrome_host), DesiredCapabilities.CHROME)
        self._chrome_host = chrome_host
        self._last_time_report = datetime.now()
        self._known_practical_sessions = set()
        self._known_theory_sessions = set()
        self._known_test_sessions = set()

        self._api_call_counter = 0
        self._refresh_counter = 0

        # todo
        send_message(self._bot_token, self._chat_id,
                     f"[Service Started]\n{datetime.now()}")

    def run(self):
        try:
            logging.info("login...")
            self._login()
            sleep(15)

        except Exception as e:
            logging.exception(e)
            send_message(self._bot_token, self._chat_id, f"[Error]\n{str(e)}")
            exit(1)

            # parse calendar every 30-150 seconds and send message if new slots are available
        while True:
            try:
                self._send_health_report()

                self._find_practical_slots()
                sleep(random.randint(5, 30))

                self._find_theory_slots()
                sleep(random.randint(5, 30))

                self._find_test_slots()

                self._smart_sleep()
                self._refresh_browser()
            except InvalidSessionIdException:
                logging.error("browser session is invalid, restart browser session...")
                self.browser = webdriver.Remote(
                    '{:}/wd/hub'.format(self._chrome_host), DesiredCapabilities.CHROME)
                self.run()
            except Exception as e:
                logging.error(
                    f"error in main loop, after  {self._api_call_counter} api calls and {self._refresh_counter} refreshes")
                logging.exception(e)
                send_message(self._bot_token, self._chat_id, f"[Error]\n{str(e)}\nrefresh and sleep 60 seconds...")
                self._refresh_browser()
                sleep(60)
                if self._is_login_page():
                    # todo put this logic to function, rerun run from scratch
                    logging.info("login again in 240 sec...")
                    sleep(240)
                    self.run()

    def _find_practical_slots(self):
        if self._practical_lesson_target is None:
            return
        logging.info(f"find practical slots,  {self._api_call_counter} api call")
        url = "https://booking.bbdc.sg/bbdc-back-service/api/booking/c2practical/listPracSlotReleased"

        payload = practical_lessons[self._practical_lesson_target]
        available_slots = self._find_slots(payload, url)

        for i in available_slots:
            i.type = "practical"
            i.lesson_name = self._practical_lesson_target

        logging.info(f"found {len(available_slots)} practical slots")
        self._notify_about_new_slots(available_slots, "practical")

        self._book_first_new_slot(available_slots)

    def _find_theory_slots(self):
        if self._theory_lesson_target is None:
            return

        logging.info(f"find theory slots,  {self._api_call_counter} api call")

        url = "https://booking.bbdc.sg/bbdc-back-service/api/booking/theory/listTheoryLessonByDate"
        payload = theoretical_lessons[self._theory_lesson_target]
        available_slots = self._find_slots(payload, url)

        for i in available_slots:
            i.type = "theory"
            i.lesson_name = self._theory_lesson_target

        logging.info(f"found {len(available_slots)} theory slots")
        self._notify_about_new_slots(available_slots, "theory")

    def _find_test_slots(self):
        if self._test_target is None:
            return

        logging.info(f"find test slot,  {self._api_call_counter} api call")

        url = "https://booking.bbdc.sg/bbdc-back-service/api/booking/test/listTheoryTestSlotWithMaxCap"
        payload = test_lessons[self._test_target]
        available_slots = self._find_slots(payload, url)

        for i in available_slots:
            i.type = "test"
            i.lesson_name = self._test_target

        logging.info(f"found {len(available_slots)} test slots")
        self._notify_about_new_slots(available_slots, "test")

    def _find_slots(self, payload, url):
        self._api_call_counter += 1

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15\'',
            'JSESSIONID': f'Bearer {self._get_jsession_id()}',
            'Cookie': f'bbdc-token=Bearer%20{self._get_auth_token()}',
            'Authorization': f'Bearer {self._get_auth_token()}',
            'Content-Type': 'application/json'
        }
        payload.pop('releasedSlotMonth', None)
        response = requests.request("POST", url, headers=headers, json=payload)
        response = response.json()
        available_slots = self._parse_available_slots_in_api_response(response)
        if len(available_slots) < 4:  # < -1 - never search next month,
            # == 0 - search next month only if current empty,
            # < n - search next month if current has fewer slots than n
            logging.warning(f"only {len(available_slots)} slots, search next month")
            payload['releasedSlotMonth'] = (datetime.now() + timedelta(days=30)).strftime("%Y%m")
            logging.warning(f"no available slots, search next month: {payload['releasedSlotMonth']}")
            response = requests.request("POST", url, headers=headers, json=payload)
            response = response.json()
            next_month_slots = self._parse_available_slots_in_api_response(response)
            available_slots.extend(next_month_slots)

        return available_slots

    def _notify_about_new_slots(self, slots: List[Slot], lesson_type: str):
        if lesson_type == "practical":
            known_sessions = self._known_practical_sessions
        elif lesson_type == "theory":
            known_sessions = self._known_theory_sessions
        elif lesson_type == "test":
            known_sessions = self._known_test_sessions

        new_slots = []
        prefix = "found slot"
        for s in slots:
            if s not in known_sessions:
                prefix = "!new slot"
                new_slots.append(s)
            logging.info(f"{prefix}: {s}, id: {s.id}")

        logging.info(f"found {len(new_slots)} new {lesson_type} slots")
        if len(new_slots) > 0:
            max_slots_per_message = 12  # to avoid long lists with far away slots
            new_slots.sort(key=lambda x: x.start_time)
            new_slots = new_slots[:max_slots_per_message]
            self._last_time_report = datetime.now()
            body = '\n'.join([str(s) for s in new_slots])
            send_message(self._bot_token, self._chat_id, f"[New slot]\n{body}")

        known_sessions.clear()
        known_sessions.update(set(slots))

    @staticmethod
    def _parse_available_slots_in_api_response(slots: dict):
        available_slots = []
        slots_by_date = slots['data']['releasedSlotListGroupByDay']

        if slots_by_date is None:
            return []

        for date_str, slots in slots_by_date.items():
            for slot in slots:
                if slot['bookingProgress'] == 'Available':
                    day = datetime.strptime(slot['slotRefDate'], '%Y-%m-%d %H:%M:%S')

                    start_time = datetime.strptime(slot['startTime'], "%H:%M")
                    start_time = day + timedelta(hours=start_time.hour, minutes=start_time.minute)

                    end_time = datetime.strptime(slot['endTime'], "%H:%M")
                    end_time = day + timedelta(hours=end_time.hour, minutes=end_time.minute)

                    available_slots.append(Slot(
                        slot['slotId'],
                        slot['slotRefName'],
                        start_time,
                        end_time,
                        slot['slotIdEnc'],
                        slot['bookingProgressEnc']
                    ))
        return available_slots

    def _book_first_new_slot(self, slots: List[Slot]):
        if len(slots) == 0:
            return

        if self._auto_booking is False:
            return

        slots.sort(key=lambda x: x.start_time)

        for slot in slots:
            # skip far slots
            if slot.start_time - datetime.now() > timedelta(days=5):
                logging.warning(f"slot {slot} is too far, skip")
                return  # slots are sorted by date, so we can stop here

            # skip early morning or late night slots
            if slot.start_time.hour < 9 or slot.start_time.hour > 20:
                logging.warning(f"slot {slot} is too early or late, skip")
                continue

            # skip eng lessons, tuesday and friday 6pm-7pm, you can set skip your working hours here
            if (slot.start_time.isoweekday() == 2 or slot.start_time.isoweekday() == 5) \
                    and slot.start_time.time() < time(19, 00) and time(18, 00) < slot.end_time.time():
                logging.warning(f"slot {slot} slot intersects with eng lesson, skip")
                continue

            # # force book
            # if 9 <= slot.start_time.hour < 12 and slot.start_time - datetime.now() < timedelta(
            #         hours=3):  # todo book 9-11:30 slot anyway 3h in advance
            #     send_message(self._bot_token, self._chat_id, f"!!! book non canceled slot {slot}")
            #     self._book_slot(slot)
            #     return

            # skip non-cancelable slots, but notify additionally in telegram
            if slot.start_time - datetime.now() < timedelta(hours=24):
                logging.warning(f"slot {slot} is too close, skip and notify")
                send_message(self._bot_token, self._chat_id, f"slot {slot} is too early or late, skip")
                continue

            # book slot
            send_message(self._bot_token, self._chat_id, f"book slot {slot}")
            self._book_slot(slot)
            return

    def _book_slot(self, slot):
        self._api_call_counter += 1
        logging.info(f"book practical slots,  {self._api_call_counter} api call")
        url = "https://booking.bbdc.sg/bbdc-back-service/api/booking/c2practical/callBookPracticalSlot"
        payload = {"courseType": "2B",
                   "slotIdList": [slot.id],
                   "encryptSlotList": [
                       {
                           "slotIdEnc": slot.id_enc,
                           "bookingProgressEnc": slot.booking_progress_enc
                       }],
                   "insInstructorId": "",
                   "subVehicleType": "Circuit"}  # todo check road for road
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15\'',
            'JSESSIONID': f'Bearer {self._get_jsession_id()}',
            'Cookie': f'bbdc-token=Bearer%20{self._get_auth_token()}',
            'Authorization': f'Bearer {self._get_auth_token()}',
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, json=payload)
        logging.info(f"booking response: {response}")
        logging.info(f"booking body response: {response.json()}")
        self._auto_booking = False

    def _is_login_page(self) -> bool:
        if self.browser.current_url.startswith("https://booking.bbdc.sg/#/login"):
            return True
        if len(self.browser.find_elements(By.ID, 'input-8')) > 0:
            return True
        return False

    @staticmethod
    def _smart_sleep():
        # Get the current date and time in the Singapore time zone
        sg_timezone = timezone(timedelta(hours=8))
        now = datetime.now(tz=sg_timezone)
        hour = now.hour

        # Sleep for 15-45 minutes between 1 AM and 5 AM Singapore time
        if 2 <= hour < 5:
            sleep_time = random.randint(2700, 3600)  # 15-45 minutes in seconds
        else:
            sleep_time = random.randint(60, 240)  # 1-4 minutes in seconds

        # Sleep for the calculated amount of time
        logging.info(f"Wait for {sleep_time} seconds...")
        sleep(sleep_time)

    def _refresh_browser(self):
        self._refresh_counter += 1
        self.browser.refresh()

    def _send_health_report(self):
        health_report_timing = 60
        if datetime.now() > self._last_time_report + timedelta(minutes=health_report_timing):
            logging.info(f"no new slots found for {health_report_timing} minutes, send health report...")
            send_message(self._bot_token, self._chat_id,
                         f"[Health report]\n no new slots found for {health_report_timing} minutes")
            self._last_time_report = datetime.now()

    def _login(self):
        self.browser.get('https://booking.bbdc.sg/#/login')

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

    def _get_auth_token(self) -> str:
        self.browser.get_cookies()
        for cookie in self.browser.get_cookies():
            if cookie['name'] == 'bbdc-token':
                token_header = cookie['value']
                break

        _, auth_token = token_header.split("%20")
        return auth_token

    def _get_jsession_id(self) -> str:
        try:
            wait = WebDriverWait(self.browser, 60)
            wait.until(EC.visibility_of_element_located((By.ID, 'app')))
        except TimeoutException:
            # try to refresh the browser and take second attempt to get jsessionid,
            # if the second attempt doesn't help, raise exception
            logging.error("timeout waiting for jsessionid")
            self.browser.save_screenshot(f"{datetime.now()}__screenshot.png")
            self.browser.refresh()
            wait = WebDriverWait(self.browser, 60)
            wait.until(EC.visibility_of_element_located((By.ID, 'app')))

        res = self.browser.execute_script("return window.localStorage;")
        jsession = json.loads(res.get("vuex"))['user']['authToken']
        _, jsessionid = jsession.split(" ")

        return jsessionid
