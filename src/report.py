import codecs
import datetime as dt
import os
from configparser import ConfigParser

import xlsxwriter

from src.models import RegisterPayment, SinglePayment


class Report:
    def __init__(self):
        self.cfg = ConfigParser()
        self.cfg.read_file(codecs.open("config.ini", "r", "utf-8"))
        self.date = dt.datetime.strptime(self.cfg["dir"]["day"], "%d.%m.%Y").date()
        self.report_titles = self.cfg["title"]["table"].split(";")
        self.title_size = [15, 15, 22, 46, 46]
        try:
            os.makedirs(self.cfg["title"]["report"])
        except FileExistsError:
            pass

    def check_payer(self, payment):
        is_match = False
        payer = payment.payer
        debtor = payment.fine.debtor
        code = payment.payer_code
        if payer is not None and debtor is not None:
            if payer.find(self.cfg["title"]["forced"]) != -1:
                is_match = True
            elif payer.find(debtor) != -1:
                is_match = True
            elif debtor.find(payer) != -1:
                is_match = True
            elif code == payment.fine.debtor_code and code != 0:
                is_match = True
        return is_match

    def save_report(self):
        with xlsxwriter.Workbook(
            f"{self.cfg['title']['report']}\\{self.cfg['dir']['day']}.xlsx"
        ) as workbook:
            titles = workbook.add_format(
                {"bold": True, "align": "center", "valign": "vcenter", "border": 1}
            )
            nums = workbook.add_format(
                {"align": "center", "valign": "top", "border": 1}
            )
            amount = workbook.add_format(
                {
                    "num_format": "# ### ##0.00",
                    "align": "right",
                    "valign": "top",
                    "border": 1,
                }
            )
            text = workbook.add_format(
                {"text_wrap": True, "valign": "top", "border": 1}
            )

            worksheet = workbook.add_worksheet(f"{self.cfg['dir']['day']}")

            for i, title in enumerate(self.report_titles):
                worksheet.write(0, i, title, titles)
                worksheet.set_column(i, i, self.title_size[i])

            single_payments = SinglePayment.select().where(
                SinglePayment.date == self.date,
                SinglePayment.fine.is_null(False),
            )

            register_payments = RegisterPayment.select().where(
                RegisterPayment.date == self.date
            )

            i = 1
            for payment in single_payments.objects():
                worksheet.write(i, 0, payment.num, nums)
                worksheet.write(i, 1, payment.amount, amount)
                worksheet.write(i, 2, payment.fine.number, nums)
                worksheet.write(i, 3, payment.payer, text)
                worksheet.write(i, 4, payment.fine.debtor, text)
                i += 1

            for payment in register_payments.objects():
                if not self.check_payer(payment):
                    worksheet.write(
                        i, 0, str(payment.num) + "/" + str(payment.payorder_id), nums
                    )
                    worksheet.write(i, 1, payment.amount, amount)
                    worksheet.write(i, 2, payment.fine.number, nums)
                    worksheet.write(i, 3, payment.payer, text)
                    worksheet.write(i, 4, payment.fine.debtor, text)
                    i += 1
