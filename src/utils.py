import codecs
import os
from configparser import ConfigParser

cfg = ConfigParser()
cfg.read_file(codecs.open("config.ini", "r", "utf-8"))


def choose_day():
    year = cfg["dir"]["year"]
    days = os.listdir(f"{year}\\{os.listdir(year)[len(os.listdir(year)) - 1]}")
    enum_days = {}
    for day in days:
        num = int(day[0:2])
        enum_days[num] = day
        print(str(num) + ")", day)
    day = int(input(cfg["lang"]["choosing day"] + " "))
    with open("config.ini", mode="w", encoding="utf-8") as config:
        cfg["dir"]["day"] = enum_days[day]
        cfg.write(config)
