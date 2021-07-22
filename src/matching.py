import codecs
import datetime as dt
import re
import time
from configparser import ConfigParser

from bs4 import BeautifulSoup as bs
from progress.bar import IncrementalBar
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        StaleElementReferenceException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

from src import models
from src.auth import Day


class Receipting(Day):
    class ElemHasClass():
        def __init__(self, locator, css_class):
            self.locator = locator
            self.css_class = css_class

        def __call__(self, driver):
            element = driver.find_element(*self.locator)
            if self.css_class in element.get_attribute("class"):
                return element
            return False

    def __init__(self, payment):
        super().__init__()
        self.cfg = ConfigParser()
        self.cfg.read_file(codecs.open("config.ini", "r", "utf-8"))
        self.payment = payment
        self.driver.implicitly_wait(20)
        self.uin_elem = None
        self.charge_uin = None

    def open_payment(self):
        self.driver.find_element_by_xpath(
            f'//*[@wicketpath="table_body_rows_{self.payment.elem_id}_cells_2"]/div/div/a/img'
        ).click()
        self.uin_elem = WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located((By.NAME, "uin"))
        )
        self.charge_uin = WebDriverWait(self.driver, 10).until(
            ec.element_to_be_clickable((By.NAME, "chargeUin"))
        )

    def check_matched(self):
        charge_tab = (
            bs(self.driver.page_source, "lxml")
            .find("tbody", wicketpath="chargeTable_body")
            .findChildren("tr")
        )
        if len(charge_tab) > 0:
            return True
        return False

    def update_payment(self):
        self.payment.payer = (
            self.driver.find_element_by_name("payerName").get_attribute("value").upper()
        )
        self.payment.payer_code = self.driver.find_element_by_name(
            "payerInn"
        ).get_attribute("value")
        self.payment.amount = (
            self.driver.find_element_by_name("paymentSum")
            .get_attribute("value")
            .replace("\xa0", "")
            .replace(",", ".")
        )
        payment_uin = re.search(
            self.cfg["pattern"]["uin"], self.uin_elem.get_attribute("value")
        )
        if payment_uin and self.payment.fine:
            self.payment.fine.uin = payment_uin.group(0)
            self.payment.fine.save()
        elif payment_uin and not self.payment.fine:
            self.payment.fine = models.Fine.create(uin=payment_uin.group(0))

    def fill(self):
        if self.payment.fine.uin:
            self.uin_elem.clear()
            self.uin_elem.send_keys(self.payment.fine.uin)
            WebDriverWait(self.driver, 10).until(
                ec.invisibility_of_element_located(
                    (By.XPATH, '//*[@class="blockUI blockOverlay"]')
                )
            )
            self.charge_uin.click()
        elif self.payment.fine.number:
            self.driver.find_element_by_name("decisionNum").send_keys(
                self.payment.fine.number
            )
        self.driver.find_element_by_name("search").click()
        try:
            WebDriverWait(self.driver, 30).until(
                ec.visibility_of_element_located(
                    (By.XPATH, '//*[@wicketpath="decisionTable_body"]/tr/td[2]/div')
                )
            )
        except TimeoutException:
            return True
        return False

    def update_fine(self):
        table = bs(self.driver.page_source, "lxml").find(
            "table", wicketpath="decisionTable"
        )
        titles = self.cfg["titles"]["payment"].split(";")
        titles_id = {}
        for i, tag in enumerate(table.thead.tr.findChildren("th")):
            if tag.text in titles:
                titles_id[tag.text] = i
        for num, tag in enumerate(table.tbody.tr.findChildren("td")):
            if titles_id[titles[0]] == num:
                self.payment.fine.number = tag.text.strip()
            elif titles_id[titles[1]] == num:
                self.payment.fine.debtor = tag.text.strip().upper()
            elif titles_id[titles[2]] == num:
                self.payment.fine.debtor_code = tag.text.strip()
        self.payment.fine.save()

    def add_founded_fine(self):
        WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located(
                (By.XPATH, '//*[@wicketpath="decisionTable_body"]/tr/td[2]/div')
            )
        ).click()
        WebDriverWait(self.driver, 10).until(
            self.ElemHasClass(
                (By.XPATH, '//*[@wicketpath="decisionTable_body"]/tr'), " row-selected"
            )
        )
        self.driver.find_element_by_name("amountDistributed").send_keys(
            (str(self.payment.amount)).replace(".", ",")
        )
        self.driver.find_element_by_name("add").click()
        WebDriverWait(self.driver, 360).until(
            ec.visibility_of_element_located(
                (
                    By.XPATH,
                    '//*[@wicketpath="chargeTable_body_rows_1_cells_1"]/div/div/a/span',
                )
            )
        )

    def save_payment(self):
        self.driver.find_element_by_name("save").click()
        time.sleep(3)

    def exit_receipting(self):
        self.payment.is_taken = True
        self.payment.save()
        self.driver.quit()
        return self.payment.is_taken


class Payments:
    def __init__(self):
        self.cfg = ConfigParser()
        self.cfg.read_file(codecs.open("config.ini", "r", "utf-8"))
        self.payments = self.get_unmatched()
        self.progress_bar = IncrementalBar(
            self.cfg["lang"]["single"], max=len(self.payments)
        )

    def get_unmatched(self):
        date = dt.datetime.strptime(self.cfg["dir"]["day"], "%d.%m.%Y").date()
        query = models.SinglePayment.select().where(
            models.SinglePayment.date == date,
            models.SinglePayment.is_taken == 0,
        )
        return query.objects()


def receipting(payment):
    manager = Receipting(payment)
    try:
        manager.open_day()
        manager.open_payment()
        manager.update_payment()
        if not manager.payment.fine:
            return manager.exit_receipting()
        if manager.check_matched():
            return manager.exit_receipting()
        if manager.fill():
            return manager.exit_receipting()
        manager.update_fine()
        manager.add_founded_fine()
        manager.save_payment()
    except (
        ElementClickInterceptedException,
        TimeoutException,
        StaleElementReferenceException,
        WebDriverException,
    ):
        manager.quit()
        return payment.is_taken
    return manager.exit_receipting()
