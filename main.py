import os
import multiprocessing as mp

from src import auth, matching, parse, utils


def main():
    reg_parser = parse.RegisterParser()
    reg_parser.open_xml_files()

    payments_parser = parse.PaymentsParser()
    payments_parser.set_types()

    manager = matching.Payments()
    payments = manager.get_unmatched()
    progress_bar = manager.progress_bar
    while len(payments) > 0:
        with mp.Pool(processes=4) as pool:
            for result in pool.imap_unordered(matching.receipting, payments):
                if result:
                    progress_bar.next()
        payments = manager.get_unmatched()
    progress_bar.finish()

    os.system("shutdown -s")


if __name__ == "__main__":
    utils.choose_day()
    auth.Login().log_in()
    main()
