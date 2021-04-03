# -*- coding: utf-8 -*-
"""
Created on Tue Nov  3 17:03:16 2020

@author: I20035
"""

import logging
import sys
import time as sleep

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [p%(process)s] [%(levelname)-5.5s] {%(filename)s:%(lineno)d} %(message)s")
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

fileHandler = logging.FileHandler("log_periodic_wirte.log")
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

rootLogger.setLevel(level=logging.DEBUG)

count = 0

def start_periodic_write():
    global count
    
    while True:
        rootLogger.info("update")
        sleep.sleep(1)
        count = count + 1
        if count > 20:
            break
    
if __name__ == '__main__':
    try:
        start_periodic_write()
    except Exception as e:
        rootLogger.exception( "exception in main thread : " + str(e) )
    except (KeyboardInterrupt, SystemExit):        
        rootLogger.exception( "keyboard inturrupt or sys exit")
    except :
        rootLogger.exception( "exception in main thread")