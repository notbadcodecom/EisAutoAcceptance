import multiprocessing as mp
import os

from src import auth, matching, parse, report, utils


def main():
    payments_parser = parse.PaymentsParser()
    payments_parser.set_types()

    manager = matching.Payments()

    payments = manager.get_unmatched()
    progress_bar = manager.get_progress_bar("single")
    while len(payments) > 0:
        with mp.Pool(processes=4) as pool:
            for result in pool.imap_unordered(matching.receipting, payments):
                if result:
                    progress_bar.next()
        payments = manager.get_unmatched()
    progress_bar.finish()

    reg_parser = parse.RegisterParser()
    reg_parser.open_xml_files()
    progress_bar = manager.get_progress_bar("register")
    for reg in manager.registers:
        matching.reg_receipting(reg)
        progress_bar.next()
    progress_bar.finish()

    report.Report().save_report()

    # os.system("shutdown /s /t 1")


if __name__ == "__main__":
    utils.choose_day()
    auth.Login().log_in()
    main()
