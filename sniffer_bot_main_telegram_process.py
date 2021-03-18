# -*- coding: utf-8 -*-
"""
Created on Mon Oct 28 18:20:09 2019

@author: Parth Pandya

about:
    telegram main thread , responsible for adding and removing new user.

referance taken from :
https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-%E2%80%93-Your-first-Bot
https://medium.com/@ManHay_Hong/how-to-create-a-telegram-bot-and-send-messages-with-python-4cf314d9fa3e

"""

import socket
import logging
import os
import sys
import telegram
from telegram.ext import Updater, InlineQueryHandler, CommandHandler
import time as sleep
from datetime import datetime,  time
import json
import threading
import _thread
from pathlib import Path

algo_start_time = time(0,2,00)
algo_end_time = time(11,56,00)

rootLogger = logging.getLogger()
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [p%(process)s] [%(levelname)-5.5s] {%(filename)s:%(lineno)d} %(message)s")

logger_dir = os.path.join( os.path.normpath(os.getcwd()), 'main_telegram_process_logs')
Path(logger_dir).mkdir(parents=True, exist_ok=True)

fileName = "log_" + os.path.basename(__file__).split(".")[0] + str(datetime.now().date()) + ".log"
logger_full_path = os.path.join( logger_dir, fileName )

fileHandler = logging.FileHandler(logger_full_path)
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

rootLogger.setLevel(level=logging.DEBUG)

# we use fixed name for sniffer bot user list.
user_json_path = r"user_list_sniffer_bot.json"


def exit_algo():

    rootLogger.info("exit_algo : closing the srcipt \n ")
    sleep.sleep(3)
    _thread.interrupt_main()


def send_data_to_broadcast_thread( input_data ):

    received = b"0"
    HOST, PORT = "localhost", 9991

    # Create a socket (SOCK_STREAM means a TCP socket)
    rootLogger.info("Sending data to back ground thread")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Connect to server and send data
            sock.connect((HOST, PORT))
            sock.sendall( input_data.encode() )

            # Receive data from the server and shut down
            received = sock.recv(1024)
        except Exception as e:
            rootLogger.exception("message : " + str(e) + "\n")
        finally:
            sock.close()

    except Exception as e:
        rootLogger.exception("message : " + str(e) + "\n")
        return received
    finally:
        if received is not None:
            return str( received, "utf-8")
        else:
            return received

def tellme(bot, update):
    chat_id = update.message.chat_id
    first_name = update.message.chat.first_name
    last_name = update.message.chat.last_name
    username = update.message.chat.username

    bot.send_message( chat_id=chat_id, text= "your user name : " + str(username) + "\nyour char id : " + str(chat_id) + \
                     "\nfirst name : "  + str(first_name) + "\nlast name : " + str(last_name) )

def add_user( bot, update, status ):

    user_dict = {}
    user_dict["id"] = update.message.chat_id
    user_dict["f"] = update.message.chat.first_name
    user_dict["l"] = update.message.chat.last_name
    user_dict["u"] = update.message.chat.username

    try:
        with open(user_json_path, 'r+') as openfile:
            user_json_data = json.load(openfile)
    except IOError:
        user_json_data = {}
        open( user_json_path, 'w+' )

    if str( user_dict["id"] ) not in user_json_data:

        user_json_data[ user_dict["id"] ] = user_dict

        with open(user_json_path, 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(user_json_data, indent=4))

        if status == "addme":
            bot.send_message( chat_id = user_dict["id"], text="User added succesfully!")
        elif status == "start":
            bot.send_message( chat_id = user_dict["id"], text="Welcome to crypto sniffer bot !!! \n" + \
                                                               "you are added succesfully. \n" + \
                                                               "to stop notification : /removeme \n" + \
                                                               "to start again : /addme \n" + \
                                                               "for more details visit website")

        telegram_data = json.dumps( {"src":"telegram", "payload" : "update_users" } )
        send_data_to_broadcast_thread(telegram_data)
        sleep.sleep(3)

    else:
        bot.send_message( chat_id = user_dict["id"], text="User already exists!")


def remove_user( bot, update ):

    user_dict = {}
    user_dict["id"] = update.message.chat_id
    user_dict["f"] = update.message.chat.first_name
    user_dict["l"] = update.message.chat.last_name
    user_dict["u"] = update.message.chat.username

    try:
        with open(user_json_path, 'r+') as openfile:
            user_json_data = json.load(openfile)
    except IOError:
        user_json_data = {}
        open( user_json_path, 'w+' )

    if str( user_dict["id"] ) in user_json_data:

        user_json_data.pop( str(user_dict["id"] ) )

        with open(user_json_path, 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(user_json_data, indent=4))

        bot.send_message( chat_id = user_dict["id"], text="User removed succesfully!")

        telegram_data = json.dumps( {"src":"telegram", "payload" : "update_users" } )
        send_data_to_broadcast_thread(telegram_data)
        sleep.sleep(3)

    else:
        bot.send_message( chat_id = user_dict["id"], text="User does not exists!")

# all telegram commands are here.
def start(bot, update):
    add_user( bot, update, "start" )

def addme(bot, update):
    add_user( bot, update , "addme" )

def removeme(bot, update):
    remove_user( bot, update )

def myhealth(bot, update):
    telegram_data = json.dumps( {"src":"telegram", "payload" : "send_health" } )
    health_status = send_data_to_broadcast_thread(telegram_data)
    if health_status is not None:
        bot.send_message( chat_id = update.message.chat_id, text = health_status)
    else:
        bot.send_message( chat_id = update.message.chat_id, text = "no status received")

def telegram_bot_thread():

    updater = Updater( '1439545509:AAErHXI63jIfkIv8tv-gUrYZjHvKoLzpqhA', use_context=False )

    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start',start))
    dp.add_handler(CommandHandler('tellme',tellme))
    dp.add_handler(CommandHandler('addme',addme))
    dp.add_handler(CommandHandler('removeme',removeme))
    dp.add_handler(CommandHandler('myhealth',myhealth))

    updater.start_polling()
    updater.idle()


def main():

    rootLogger.info("starting telegram forground thread")
    threading.Thread( target = telegram_bot_thread, \
          args = () ,\
          daemon = True ).start()
    rootLogger.info("telegram forground thread started successful")

    while True:
        sleep.sleep(5)
        time_now = datetime.now().time()
        if time_now > algo_end_time and time_now < algo_start_time:
            exit_algo()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        rootLogger.exception("message : " + str(e) + "\n")
    except:
        rootLogger.exception("some exception in telegram thread \n ")
