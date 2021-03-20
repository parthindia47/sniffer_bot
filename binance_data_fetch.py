# -*- coding: utf-8 -*-
"""
Created on Thu Aug 13 22:38:55 2020

@author: Parth Pandya

About:
    This file will be responsible for ferching price data.

development:

    1. comparision of CCXT market pairs and Binance market pair done
       - BCH , BSV have some different names anyways we don't want to
       trade there
       - aprart from that there is not much difference

    2. Now we need to focus on price and volume actions.
       - we need less resource heavey method.
       firing socket on all pair will be too much heavy and cannot run on
       smaller EC2. so socket won't be physible.

       - we basically won't to monitor price action and volume action
       at specific interval say 30 sec / 1 min. some how we need some good poling method.

    3. binance have exllent facility of socket for candles , at minimum we can get 1m
       candle, this will help us to built any other candle.

       t3.small -> 15$ one on digital ocean.

    4. uploading script on ec2 : https://www.youtube.com/watch?v=WE303yFWfV4

"""

from binance.client import Client
from binance.websockets import BinanceSocketManager
from binance.enums import *
import pprint
#import ccxt
from datetime import datetime , timedelta
import time
import time as sleep
from datetime import time as datetime_time
import sys
from decimal import Decimal
import math
import collections
from enum import IntEnum
import threading
import tweepy
from tweepy import OAuthHandler
from pytz import timezone
from dateutil import tz
import json
import statistics
#import winsound
import csv
import socketserver
import subprocess
from twisted.internet import reactor
import _thread
import os
from pathlib import Path
import signal
from telegram import Bot
from telegram.error import TimedOut
import logging

# some usful enums to access tupel and list element
class Kline_data(IntEnum):
    dT = 0    #datetime object
    iT = 1    #integer time
    O = 2     #open
    H = 3     #high
    L = 4     #low
    C = 5     #close
    V = 6     #volume
    I = 7     #interval 1m, 3m, 5m
    CHG = 8   #change
    AMP = 9   #amplitude

class Binance_Kline(IntEnum):
    OpenTime = 0
    Open = 1
    High = 2
    Low = 3
    Close = 4
    Volume = 5
    CloseTime = 6
    QuoteAssetVolume = 7
    NumberOfTrades = 8
    TakerBuybaseAssetVolume = 9
    TakerBuyquoteAssetVolume = 10
    Ignore = 11

# various client objects
client_BINANCE = None
client_TWITTER = None
telegram_bot = None
binance_obj_ccxt = None
binance_obj_ccxt_markets = None
twitt_info_dict = None

#some random globals
rootLogger = None
server = None
closing_this_script = False
coin_count_list = None
bm = None

# circular queues for storing data
process1_candle_dict_1m = {}
process2_candle_dict_1m = {}
process3_candle_dict_1m = {}
process4_candle_dict_1m = {}

process1_candle_dict_3m = {}
process2_candle_dict_3m = {}
process3_candle_dict_3m = {}
process4_candle_dict_3m = {}

process1_candle_dict_5m = {}
process2_candle_dict_5m = {}
process3_candle_dict_5m = {}
process4_candle_dict_5m = {}

# thresold values to generate signals
change_pc_thresold = 200
amp_pc_thresold = 200
minimum_sat_value = 200
vol24h_thresold = 12
lowerleg_pc_thresold = 1200
TRADE_BASE_CURRENCY = "BTC"

# this globals are used to count coins every minute.
current_time_stamp_process1 = 0
prev_time_stamp_process1 = 0
total_coin_process1 = 0

current_time_stamp_process2 = 0
prev_time_stamp_process2 = 0
total_coin_process2 = 0

current_time_stamp_process3 = 0
prev_time_stamp_process3 = 0
total_coin_process3 = 0

current_time_stamp_process4 = 0
prev_time_stamp_process4 = 0
total_coin_process4 = 0

# some locks and critical resources
dummy_trades_in_progress = {}
CHAT_IDs = []
data_lock = threading.Lock()
id_list_lock = threading.Lock()
telegram_user_list_json_path = r"user_list_sniffer_bot.json"

#timings for algo
algo_start_time = datetime_time(0,2,00)
algo_end_time = datetime_time(11,59,00)


def set_logger():

    global rootLogger

    rootLogger = logging.getLogger()
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [p%(process)s] [%(levelname)-5.5s] {%(filename)s:%(lineno)d} %(message)s")

    logger_dir = os.path.join( os.path.normpath(os.getcwd()), 'binance_data_fetch_logs')
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


def exit_script():

    global bm
    global dummy_trades_in_progress
    global data_lock
    global server
    global closing_this_script

    rootLogger.info("terminating this script aquiring data lock before that.")

    data_lock.acquire()

    rootLogger.info("closing socket manager and reactor loop")
    closing_this_script = True
    bm.close()
    reactor.stop()
    sleep.sleep(3)

    try:
        for dummy_trade_process in dummy_trades_in_progress:
            rootLogger.info("killing : " + dummy_trade_process )

            process_obj = dummy_trades_in_progress[dummy_trade_process]["proc_obj"]
            #this part to be used on linux servers.
            os.kill( process_obj.pid , signal.SIGINT)
            #process_obj.send_signal(signal.SIGINT)

            #this part works on windows.
            #process_obj.kill()
            #outs, errs = dummy_trades_in_progress[dummy_trade_process]["proc_obj"].communicate()

            trade_id = dummy_trades_in_progress[ dummy_trade_process ]["trade_id"]
            original_dict = read_key( trade_id  )
            original_dict["dummy_order_status"] = "suspended"
            write_key( trade_id, original_dict )
    except Exception as e:
        rootLogger.exception( "exception while killing process : " + str(e) )

    data_lock.release()

    sleep.sleep(2)
    rootLogger.info("closing this main thread and exiting shell")
    _thread.interrupt_main()
    sleep.sleep(2)
    os._exit(0)

#remove this in linux server
#def playsound():
#    winsound.Beep(5000, 300)


def send_telegram_msg_to_all( tlg_msg ):

    global CHAT_IDs
    global id_list_lock

    id_list_lock.acquire()

    total_members = len(CHAT_IDs)
    member_counter = 0

    while member_counter < total_members :
        try:
            telegram_bot.sendMessage( chat_id = CHAT_IDs[member_counter], text = tlg_msg)
            sleep.sleep(1)
            member_counter = member_counter + 1
        except TimedOut:
            rootLogger.exception("telegram time out exception : \n")
            sleep.sleep(3)
        except Exception as e:
            rootLogger.exception("telegram other exception : " + str(e) + "\n")
            sleep.sleep(3)
            member_counter = member_counter + 1

    id_list_lock.release()


def update_chat_id_list():

    global CHAT_IDs

    try:
        new_user_list = []
        with open(telegram_user_list_json_path) as f:
            user_json_data = json.load(f)

        if len(user_json_data) > 0 :
            for key in user_json_data:
                new_user_list.append(user_json_data[key]["id"])

    except Exception as e:
        rootLogger.exception(e)

    # update the char id list.
    id_list_lock.acquire()
    CHAT_IDs = new_user_list
    id_list_lock.release()

def set_client_Telegram():

    # set telegram client and load list of telegram users.
    global telegram_bot
    TOKEN = '1439545509:AAErHXI63jIfkIv8tv-gUrYZjHvKoLzpqhA'
    telegram_bot = Bot(token=TOKEN)
    update_chat_id_list()

class MyTCPHandler(socketserver.BaseRequestHandler):

    global id_list_lock
    global data_lock
    global CHAT_IDs
    global dummy_trades_in_progress
    global closing_this_script
    global coin_count_list

    # server must override the handle() method to implement communication to the client.
    def handle(self):

        # self.request is the TCP socket connected to the client
        data = self.request.recv(1024).strip()
        data = data.decode(encoding='UTF-8')

        if not closing_this_script:
            try:
                data = json.loads(data)

                rootLogger.info("new data received in TCP socket")
                # update the json file , we will aquire lock to update json file
                # and also to access dummy trade list.


                if "src" in data :

                    # if this message is coming from dummy trades
                    if data["src"] == "dummy_trade":

                        data_lock.acquire()

                        trade_data = data["payload"]
                        original_dict = read_key(trade_data["id"])
                        original_dict["dummy_order_excecuted"] = trade_data
                        original_dict["dummy_order_status"] = "complete"
                        write_key(trade_data["id"], original_dict)

                        del dummy_trades_in_progress[ trade_data["pair"] ]

                        #print the trade update received also need to send on telegram.

                        result_str = "trade complete : " +  \
                                     trade_data["pair"] + " " + \
                                     trade_data["results"] + " hit \n" + \
                                     " entry " + '{:.8f}'.format(trade_data["entry"]) + \
                                     " exit " + '{:.8f}'.format(trade_data["results_Price"]) + "\n"

                        rootLogger.info(result_str)

                        threading.Thread( target = send_telegram_msg_to_all , \
                              args = (result_str,) , \
                              daemon = True ).start()

                        data_lock.release()

                    #if this message is coming from telegram thread
                    elif data["src"] == "telegram":
                        if data["payload"] == "update_users":
                            rootLogger.info("update telegram users")
                            # lock is aquired inside call
                            update_chat_id_list()
                        if data["payload"] == "send_health":
                            self.request.sendto( str(coin_count_list).encode() , self.client_address )


            except Exception as e:
                rootLogger.exception("socket : may be not valid json" + str(e))


def tcp_server_thread():

    global server

    HOST, PORT = "localhost", 9991
    # Create the server, binding to localhost on port 9999
    try:
        server = socketserver.TCPServer((HOST, PORT), MyTCPHandler)
        server.allow_reuse_address = True
        server.serve_forever()
    except Exception as e:
        rootLogger.info(e)
        return None

# note : write_key will overwrite even if given key already exists.
def write_key( key, value ):

    signal_dir = os.path.join(os.path.normpath(os.getcwd()), 'trade_signals_dir')
    Path(signal_dir).mkdir(parents=True, exist_ok=True)

    time_format = "%Y_%m_%d_%H_%M_%S"
    time_now = datetime.now().date().strftime(time_format)
    fileName = "signals_detected_" + time_now + ".json"

    jsonFilePath = os.path.join(signal_dir, fileName)

    try:
        with open(jsonFilePath, 'r+') as openfile:
            json_object = json.load(openfile)
    except IOError:
        json_object = {}
        open(jsonFilePath, 'w+')

    if key is not None:
        json_object[key] = value

        with open(jsonFilePath, 'w+', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(json_object, default=str, indent=4 ))
        return True
    else:
        return None

def read_key( key ):

    signal_dir = os.path.join(os.path.normpath(os.getcwd()), 'trade_signals_dir')
    Path(signal_dir).mkdir(parents=True, exist_ok=True)

    time_format = "%Y_%m_%d_%H_%M_%S"
    time_now = datetime.now().date().strftime(time_format)
    fileName = "signals_detected_" + time_now + ".json"

    jsonFilePath = os.path.join(signal_dir, fileName)

    try:
        with open(jsonFilePath, 'r+') as openfile:
            json_object = json.load(openfile)
    except:
        json_object = {}
        open(jsonFilePath, 'w+')

    if key is not None and key in json_object:
        return json_object[key]
    else:
        return None

def set_client_BINANCE():

    global client_BINANCE
    client_BINANCE = Client("kmqYFcd3ArdkKSpNjX0X6UJvrPnmnEvE6v0ibCJGpiOijVA4bhLPqdjlM9VNWnig",\
                            "hDJX0GJGbQSaLGISaWK4vs9Fx5aQLj3xFk4jUGz5VmSv74tCf2XqU4ct3ROPZe6u")

def set_client_CCXT():

    global binance_obj_ccxt
    global binance_obj_ccxt_markets

    binance_obj_ccxt  = ccxt.binance()
    binance_obj_ccxt_markets = binance_obj_ccxt.load_markets()

def set_client_TWITTER():

    global twitt_info_dict
    global client_TWITTER

    #Variables that contains the user credentials to access Twitter API
    access_token = "1107323750322565120-DSt623ScZWrEWVHKutoZhKuFVaT4AR"
    access_token_secret = "ho2jKpqQDYGvHmYU3xZWLvJi6NcQ0fBBSpV8sGDK7hBlz"
    consumer_key = "jjOItHZUspNcY3HxNioQ6cOla"
    consumer_secret = "KCKP5dyxn1yd0QgpYDVmdpnUaCfarkRWH0FBPDbaRHv7jcyL58"

    # read list of all twitter accounts for different coins.
    with open( "coin_twitterDB_SymbolAsKey.json" ) as f:
        twitt_info_dict = json.load(f)

    #This handles Twitter authetification and the connection to Twitter Streaming API
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    client_TWITTER = tweepy.API(auth)


# function will return top 3 activity of given crypto
# input : name of any cryto as per BINANCE
# return : most recent 3 tweet activity
# note : need to run set_client_TWITTER() before using this.
def get_twitter_timeline( crypto_name ):

    tweet_list = []
    Max_twitts = 1

    if crypto_name in twitt_info_dict:
        crypto_twitter_ID = twitt_info_dict[crypto_name]["id"]
    else:
        return None

    tweets = client_TWITTER.user_timeline( id = crypto_twitter_ID, count = 10 )

    for tweet in tweets:

        if len(tweet_list) >= Max_twitts:
            return tweet_list

        datetime_utc = tweet.created_at.replace( tzinfo = tz.gettz('UTC') )
        india_tweet_time = datetime_utc.astimezone( timezone('Asia/Kolkata') )
        india_tweet_time = india_tweet_time.replace(tzinfo=None)

        tweet_link = "https://twitter.com/" + tweet.user.screen_name + "/status/" + tweet.id_str
        account_link = "https://twitter.com/" + tweet.user.screen_name

        #if someone retweets
        tweet_type = None
        if hasattr(tweet, 'retweeted_status') :
            tweet_type = "retweeted"

        #if someone retweeted and commented also
        elif tweet.is_quote_status == True:
            tweet_type = "quoted"

        # user have replied to some account
        elif tweet.in_reply_to_status_id_str is None:

            tweet_type = "original_tweet"

        if tweet_type is not None:
            tweet_list.append( { "type" : tweet_type , \
                                 "time" : india_tweet_time, \
                                 "text" : tweet.text, \
                                 "tweet_link" : tweet_link,\
                                 "account_link" : account_link } )

    #if it ever comes here just return the list.
    return tweet_list

#this will return list of coins availible with given pair
#this function uses BINANCE APIs
def get_all_market_for_given_base_BINANCE(base_currency):

    if base_currency is not None and isinstance( base_currency , str):

        all_tickers = client_BINANCE.get_all_tickers()
        len_base = len(base_currency)
        pair_list = []

        for ticker in all_tickers:
            if ticker['symbol'][-len_base:] == base_currency:
                pair_list.append(ticker['symbol'])
        return pair_list
    else:
        return None

#this will return list of coins availible with given pair
#this function uses CCXT APIs
def get_all_market_for_given_base_CCXT( base_currency ):

    if base_currency is not None and isinstance( base_currency , str):

        all_tickers = binance_obj_ccxt.symbols

        base_currency = "/" + base_currency
        pair_list = []

        for ticker in all_tickers:
            if base_currency in ticker:
                ticker = ticker.replace("/","")
                pair_list.append(ticker)

        return pair_list
    else:
        return None

#give name of coin from trading pair.
def get_symbol_name_from_pair( alert_symbol_pair , base_currency ):
    return alert_symbol_pair[:-len(base_currency)]

def get_int_interval_from_str( str_interval ):
    return int(str_interval[:-1])


def generate_alert( alert_symbol_pair, candle_tupel ):

    global dummy_trades_in_progress
    alert_data_dict = {}

    data24hr = client_BINANCE.get_ticker(symbol = alert_symbol_pair)
    #volume24hr_trade_coin = int( round( data24hr["volume"], 0 ) )
    volume24hr_base_coin  = int( round( float( data24hr["quoteVolume"] ) ,0) )

    interval = get_int_interval_from_str( candle_tupel[ Kline_data.I ] )

    if ( volume24hr_base_coin > vol24h_thresold and int( candle_tupel[Kline_data.C]*100000000 ) > minimum_sat_value ) :

        alert_data_dict["pair"] = alert_symbol_pair
        alert_data_dict["candle"] = candle_tupel
        alert_data_dict["24h_base_volume"] = volume24hr_base_coin

        # get twitter information about this coin
        twitt_list = get_twitter_timeline( get_symbol_name_from_pair(alert_symbol_pair, TRADE_BASE_CURRENCY) )

        if twitt_list is not None and len(twitt_list) > 0:
            # this can be negative also if latest tweet came after candle
            last_activity_age = ( candle_tupel[ Kline_data.dT ] - twitt_list[0]["time"] ).total_seconds()
            alert_data_dict["last_tweet_age_sec"] = int(last_activity_age)
            alert_data_dict["last_tweet_age_min"] = int(last_activity_age/60.0)
            alert_data_dict["last_tweet_activities"] = twitt_list
        else:
            alert_data_dict["last_tweet_age_sec"] = None
            alert_data_dict["last_tweet_age_min"] = None
            alert_data_dict["last_tweet_activities"] = None

        # fetch last 21 candles of same time frame to see volume breakout on same time frame
        candles = client_BINANCE.get_historical_klines( alert_symbol_pair, \
                                                candle_tupel[ Kline_data.I ], \
                                                start_str = candle_tupel[ Kline_data.iT ] - 20*interval*60*1000, \
                                                end_str = candle_tupel[ Kline_data.iT ] )

        if len(candles) == 21 and ( candles[-1][Binance_Kline.OpenTime] == candle_tupel[ Kline_data.iT ] ):

            current_candle_volume = float( candles[-1][Binance_Kline.QuoteAssetVolume] )
            del candles[-1]

            volume_list = []
            zero_volume_counter = 0
            for candle in candles:
                volume_list.append( float ( candle[Binance_Kline.QuoteAssetVolume] ) )

                if int ( float( candle[Binance_Kline.Volume] ) ) == 0:
                    zero_volume_counter = zero_volume_counter + 1

            average_volume_20 = statistics.mean(volume_list)
            sdeviation_volume_20 = statistics.pstdev(volume_list)

            if average_volume_20 == 0:
                average_volume_20 = 1

            volume_pc_change = round(( current_candle_volume - average_volume_20) * 100 / average_volume_20, 2)
            volume_pc_change = int( volume_pc_change*100 )

            alert_data_dict["curr_candle_volume"] = current_candle_volume
            alert_data_dict["volume_prev_20MA"] = average_volume_20
            alert_data_dict["volume_prev_20SD"] = sdeviation_volume_20
            alert_data_dict["volume_PC_change"] = volume_pc_change
            alert_data_dict["zero_volume_counter"] = zero_volume_counter
            alert_data_dict["candles_received"] = None #candles

        else:
            alert_data_dict["curr_volume"] = None
            alert_data_dict["prev_20MA"] = None
            alert_data_dict["prev_20SD"] = None
            alert_data_dict["volume_PC_change"] = None
            alert_data_dict["zero_volume_counter"] = None
            alert_data_dict["candles_received"] = None #candles

        alert_data_dict["tradeID"] = alert_symbol_pair + "_"+ \
                             str(candle_tupel[ Kline_data.iT ]) + "_" +\
                             str(candle_tupel[ Kline_data.dT ].hour).zfill(2) + \
                             str(candle_tupel[ Kline_data.dT ].minute).zfill(2) + "_" +\
                             str(candle_tupel[ Kline_data.I ]) + "_"+ \
                             "C" + str(candle_tupel[ Kline_data.CHG ]) + "_" +\
                             "A" + str(candle_tupel[ Kline_data.AMP ]) + "_"

        if alert_data_dict["last_tweet_age_min"] is not None:
           alert_data_dict["tradeID"] = alert_data_dict["tradeID"] + "T" + str(alert_data_dict["last_tweet_age_min"])
        else:
           alert_data_dict["tradeID"] = alert_data_dict["tradeID"] + "Tx"

        #============================================================

        if alert_data_dict["last_tweet_age_min"] is not None and alert_data_dict["last_tweet_age_min"] < 15:

            data_lock.acquire()
            #log this call some where and if possible start a dummy trade.
            if alert_data_dict["pair"] not in dummy_trades_in_progress:

                order_pc = 0.5
                dummy_order_entry_price = alert_data_dict["candle"][ Kline_data.C ] + \
                                          ( order_pc * alert_data_dict["candle"][ Kline_data.C ] )/100.0

                dummy_order_entry_price = round( dummy_order_entry_price , 8)

                dummy_order_dict = { "pair" : alert_data_dict["pair"], \
                                     "id": alert_data_dict["tradeID"] , \
                                     "entry" : dummy_order_entry_price , \
                                     "TP" : 8.0, \
                                     "SL" : 1.5, \
                                     "target_type" :  "pc", \
                                     "order_type" : "SLM"}

                alert_data_dict["dummy_order_fired"] = dummy_order_dict
                alert_data_dict["dummy_order_status"] = "pending"

                # start dummy order in background.
#                proc_obj = subprocess.Popen( [ "python3", "binance_dummy_trade.py", json.dumps(alert_data_dict["dummy_order_fired"]) ] , shell = False )
#                dummy_trades_in_progress[ alert_data_dict["pair"] ] = { "proc_obj" : proc_obj , \
#                                                                       "trade_id" : alert_data_dict["tradeID"] }



                telegram_msg_string = alert_symbol_pair + "\n" + \
                                      "candle time: " + str(candle_tupel[ Kline_data.dT ].hour).zfill(2) + ":" + \
                                      str(candle_tupel[ Kline_data.dT ].minute).zfill(2) + "\n" + \
                                      "candle interval: " + str(candle_tupel[ Kline_data.I ]) + "\n" + \
                                      "%change: " + str(candle_tupel[ Kline_data.CHG ] / 100.0) + "\n" + \
                                      "%amplitude: " + str(candle_tupel[ Kline_data.AMP ] / 100.0) + "\n" + \
                                      "O: " + '{:.8f}'.format( candle_tupel[ Kline_data.O ] ) + "\n" + \
                                      "H: " + '{:.8f}'.format( candle_tupel[ Kline_data.H ] ) + "\n" + \
                                      "L: " + '{:.8f}'.format( candle_tupel[ Kline_data.L ] ) + "\n" + \
                                      "C: " + '{:.8f}'.format( candle_tupel[ Kline_data.C ] ) + "\n" + \
                                      "tweet time: " + str(twitt_list[0]["time"].hour).zfill(2) + ":" + \
                                      str(twitt_list[0]["time"].minute).zfill(2) + "\n" + \
                                      "last tweet : " + str(alert_data_dict["last_tweet_age_min"]) + " min ago \n" + \
                                      "text: " + twitt_list[0]["text"] + "\n \n \n" + \
                                      "link: " + twitt_list[0]["tweet_link"]

                threading.Thread( target = send_telegram_msg_to_all , \
                                  args = (telegram_msg_string,) , \
                                  daemon = True ).start()

            #always log the signal.
            write_key( alert_data_dict["tradeID"], alert_data_dict )
            data_lock.release()
        else:
            #even doesn't match criteria just log this.
            data_lock.acquire()
            write_key( alert_data_dict["tradeID"], alert_data_dict )
            data_lock.release()

        #irrepective of anything log the call
        rootLogger.info("new signal detected : " + alert_data_dict["tradeID"] + "\n" )
        #threading.Thread( target = playsound, daemon = True ).start()


def background_process_awake():
    global coin_count_list
    sleep.sleep(30)


    coin_count_csv_dir = os.path.join(os.path.normpath(os.getcwd()), 'coin_count_dir')
    Path(coin_count_csv_dir).mkdir(parents=True, exist_ok=True)

    time_format = "%Y_%m_%d_%H_%M_%S"
    date_now = datetime.now().date().strftime(time_format)
    time_now = datetime.now().strftime(time_format)
    csv_filename = "coin_count_" + date_now  +".csv"

    csv_filepath = os.path.join( coin_count_csv_dir, csv_filename )

    coin_count_list = [str(time_now), str(total_coin_process1) , str(total_coin_process2) , \
                       str(total_coin_process3) , str(total_coin_process4) ]

    with open(csv_filepath, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(coin_count_list)


def process_message1(msg):

    global process1_candle_dict_1m
    global process1_candle_dict_3m
    global process1_candle_dict_5m

    global current_time_stamp_process1
    global prev_time_stamp_process1
    global total_coin_process1

    if msg['e'] == 'kline' and msg['k']['x'] == True:

        # code to understand start of messages
        current_time_stamp_process1 = int( round(time.time() * 1000) )
        diff_time_stamp = current_time_stamp_process1 - prev_time_stamp_process1

        if prev_time_stamp_process1 != 0 and diff_time_stamp > 15000 :
            #rootLogger.info("total coin last minute : " + str(total_coin_process1))
            total_coin_process1 = 0
            threading.Thread( target = background_process_awake, daemon = True ).start()

        #rootLogger.info( "diff " + str( diff_time_stamp ))
        total_coin_process1 = total_coin_process1 + 1
        prev_time_stamp_process1 = current_time_stamp_process1


        candle_datetime = datetime.fromtimestamp( msg['k']['t'] / 1e3 )

        #####################################################
        curr_open = float(msg['k']['o'])
        curr_high = float(msg['k']['h'])
        curr_low = float(msg['k']['l'])
        curr_closing = float(msg['k']['c'])

        # calculate % change for given time frame
        if len( process1_candle_dict_1m[ msg['s'] ] ) >= 1 :
            prev_closing = process1_candle_dict_1m[ msg['s'] ][-1][ Kline_data.C ]
            chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
            chg = int( chg*100 )
        else:
            chg = 0

        amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
        amp = int( amp*100 )

        process1_candle_dict_1m[ msg['s'] ].append( (candle_datetime, \
                                                   msg['k']['t'], \
                                                   curr_open, \
                                                   curr_high, \
                                                   curr_low, \
                                                   curr_closing, \
                                                   float( msg['k']['v'] ), \
                                                   msg['k']['i'],\
                                                   chg ,\
                                                   amp ) )

#        with open("candle_details.txt", "a") as file1:
#            file1.write(str(process1_candle_dict_1m[ msg['s'] ][-1]) + "\n")

        if chg > change_pc_thresold or amp > amp_pc_thresold:
            threading.Thread( target = generate_alert, \
              args = ( msg['s'], process1_candle_dict_1m[ msg['s'] ][-1] ) ,\
              daemon = True ).start()


        ####################################################
        # check if 3 minutes have passed
        if ( candle_datetime.minute + 1 ) % 3 == 0:
            # Let say worst situation is 1 2 | 2 X X
            if len(process1_candle_dict_1m[ msg['s']] ) > 3:
                # now we will use last 3 entries to calculate a candle

                curr_open = process1_candle_dict_1m[ msg['s']][-3][ Kline_data.O ]
                curr_closing = process1_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                         process1_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                         process1_candle_dict_1m[ msg['s']][-3][ Kline_data.H ] ])

                curr_low = min( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                         process1_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                         process1_candle_dict_1m[ msg['s']][-3][ Kline_data.L ] ])

                total_volume = sum( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                             process1_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                             process1_candle_dict_1m[ msg['s']][-3][ Kline_data.V] ])

                # calculate % change for given time frame
                if len( process1_candle_dict_3m[ msg['s'] ] ) >= 1 :
                    prev_closing = process1_candle_dict_3m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )

                process1_candle_dict_3m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=2),\
                                                          msg['k']['t'] - 2*60*1000,\
                                                          curr_open , \
                                                          curr_high ,\
                                                          curr_low ,\
                                                          curr_closing, \
                                                          total_volume ,\
                                                          "3m",\
                                                          chg,\
                                                          amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process1_candle_dict_3m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process1_candle_dict_3m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

        #####################################################
        # check if 5 minutes have passed
        if ( candle_datetime.minute + 1 ) % 5 == 0:
            if len(process1_candle_dict_1m[ msg['s']]) > 5:

                curr_open = process1_candle_dict_1m[ msg['s']][-5][ Kline_data.O ]

                curr_closing = process1_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                                  process1_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                                  process1_candle_dict_1m[ msg['s']][-3][ Kline_data.H ],\
                                  process1_candle_dict_1m[ msg['s']][-4][ Kline_data.H ],\
                                  process1_candle_dict_1m[ msg['s']][-5][ Kline_data.H ] ] )

                curr_low = min( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                                  process1_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                                  process1_candle_dict_1m[ msg['s']][-3][ Kline_data.L ],\
                                  process1_candle_dict_1m[ msg['s']][-4][ Kline_data.L ],\
                                  process1_candle_dict_1m[ msg['s']][-5][ Kline_data.L ] ] )

                total_volume = sum( [ process1_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                                      process1_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                                      process1_candle_dict_1m[ msg['s']][-3][ Kline_data.V ],\
                                      process1_candle_dict_1m[ msg['s']][-4][ Kline_data.V ],\
                                      process1_candle_dict_1m[ msg['s']][-5][ Kline_data.V ] ] )

                # calculate % change for given time frame
                if len( process1_candle_dict_5m[ msg['s'] ] ) >= 1 :
                    prev_closing = process1_candle_dict_5m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )


                # now we will use last 5 entries to calculate a candle
                process1_candle_dict_5m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=4),\
                                         msg['k']['t'] - 4*60*1000,\
                                         curr_open,\
                                         curr_high ,\
                                         curr_low ,\
                                         curr_closing,\
                                         total_volume ,\
                                         "5m",\
                                         chg,\
                                         amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process1_candle_dict_5m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process1_candle_dict_5m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

def process_message2(msg):

    global process2_candle_dict_1m
    global process2_candle_dict_3m
    global process2_candle_dict_5m

    global current_time_stamp_process2
    global prev_time_stamp_process2
    global total_coin_process2

    if msg['e'] == 'kline' and msg['k']['x'] == True:

        # code to understand start of messages
        current_time_stamp_process2 = int( round(time.time() * 1000) )
        diff_time_stamp = current_time_stamp_process2 - prev_time_stamp_process2

        if prev_time_stamp_process2 != 0 and diff_time_stamp > 15000 :
            #rootLogger.info("total coin last minute : " + str(total_coin_process2))
            total_coin_process2 = 0
            #threading.Thread( target = background_process_awake, daemon = True ).start()

        #rootLogger.info( "diff " + str( diff_time_stamp ))
        total_coin_process2 = total_coin_process2 + 1
        prev_time_stamp_process2 = current_time_stamp_process2


        candle_datetime = datetime.fromtimestamp( msg['k']['t'] / 1e3 )

        #####################################################
        curr_open = float(msg['k']['o'])
        curr_high = float(msg['k']['h'])
        curr_low = float(msg['k']['l'])
        curr_closing = float(msg['k']['c'])

        # calculate % change for given time frame
        if len( process2_candle_dict_1m[ msg['s'] ] ) >= 1 :
            prev_closing = process2_candle_dict_1m[ msg['s'] ][-1][ Kline_data.C ]
            chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
            chg = int( chg*100 )
        else:
            chg = 0

        amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
        amp = int( amp*100 )

        process2_candle_dict_1m[ msg['s'] ].append( (candle_datetime, \
                                                   msg['k']['t'], \
                                                   curr_open, \
                                                   curr_high, \
                                                   curr_low, \
                                                   curr_closing, \
                                                   float( msg['k']['v'] ), \
                                                   msg['k']['i'],\
                                                   chg ,\
                                                   amp ) )

#        with open("candle_details.txt", "a") as file1:
#            file1.write(str(process2_candle_dict_1m[ msg['s'] ][-1]) + "\n")

        if chg > change_pc_thresold or amp > amp_pc_thresold:
            threading.Thread( target = generate_alert, \
              args = ( msg['s'], process2_candle_dict_1m[ msg['s'] ][-1] ) ,\
              daemon = True ).start()


        ####################################################
        # check if 3 minutes have passed
        if ( candle_datetime.minute + 1 ) % 3 == 0:
            # Let say worst situation is 1 2 | 2 X X
            if len(process2_candle_dict_1m[ msg['s']] ) > 3:
                # now we will use last 3 entries to calculate a candle

                curr_open = process2_candle_dict_1m[ msg['s']][-3][ Kline_data.O ]
                curr_closing = process2_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                         process2_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                         process2_candle_dict_1m[ msg['s']][-3][ Kline_data.H ] ])

                curr_low = min( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                         process2_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                         process2_candle_dict_1m[ msg['s']][-3][ Kline_data.L ] ])

                total_volume = sum( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                             process2_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                             process2_candle_dict_1m[ msg['s']][-3][ Kline_data.V] ])

                # calculate % change for given time frame
                if len( process2_candle_dict_3m[ msg['s'] ] ) >= 1 :
                    prev_closing = process2_candle_dict_3m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )

                process2_candle_dict_3m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=2),\
                                                          msg['k']['t'] - 2*60*1000,\
                                                          curr_open , \
                                                          curr_high ,\
                                                          curr_low ,\
                                                          curr_closing, \
                                                          total_volume ,\
                                                          "3m",\
                                                          chg,\
                                                          amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process2_candle_dict_3m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process2_candle_dict_3m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

        #####################################################
        # check if 5 minutes have passed
        if ( candle_datetime.minute + 1 ) % 5 == 0:
            if len(process2_candle_dict_1m[ msg['s']]) > 5:

                curr_open = process2_candle_dict_1m[ msg['s']][-5][ Kline_data.O ]

                curr_closing = process2_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                                  process2_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                                  process2_candle_dict_1m[ msg['s']][-3][ Kline_data.H ],\
                                  process2_candle_dict_1m[ msg['s']][-4][ Kline_data.H ],\
                                  process2_candle_dict_1m[ msg['s']][-5][ Kline_data.H ] ] )

                curr_low = min( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                                  process2_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                                  process2_candle_dict_1m[ msg['s']][-3][ Kline_data.L ],\
                                  process2_candle_dict_1m[ msg['s']][-4][ Kline_data.L ],\
                                  process2_candle_dict_1m[ msg['s']][-5][ Kline_data.L ] ] )

                total_volume = sum( [ process2_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                                      process2_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                                      process2_candle_dict_1m[ msg['s']][-3][ Kline_data.V ],\
                                      process2_candle_dict_1m[ msg['s']][-4][ Kline_data.V ],\
                                      process2_candle_dict_1m[ msg['s']][-5][ Kline_data.V ] ] )

                # calculate % change for given time frame
                if len( process2_candle_dict_5m[ msg['s'] ] ) >= 1 :
                    prev_closing = process2_candle_dict_5m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )


                # now we will use last 5 entries to calculate a candle
                process2_candle_dict_5m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=4),\
                                         msg['k']['t'] - 4*60*1000,\
                                         curr_open,\
                                         curr_high ,\
                                         curr_low ,\
                                         curr_closing,\
                                         total_volume ,\
                                         "5m",\
                                         chg,\
                                         amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process2_candle_dict_5m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process2_candle_dict_5m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

def process_message3(msg):

    global process3_candle_dict_1m
    global process3_candle_dict_3m
    global process3_candle_dict_5m

    global current_time_stamp_process3
    global prev_time_stamp_process3
    global total_coin_process3

    if msg['e'] == 'kline' and msg['k']['x'] == True:

        # code to understand start of messages
        current_time_stamp_process3 = int( round(time.time() * 1000) )
        diff_time_stamp = current_time_stamp_process3 - prev_time_stamp_process3

        if prev_time_stamp_process3 != 0 and diff_time_stamp > 15000 :
            #rootLogger.info("total coin last minute : " + str(total_coin_process3))
            total_coin_process3 = 0
            #threading.Thread( target = background_process_awake, daemon = True ).start()

        #rootLogger.info( "diff " + str( diff_time_stamp ))
        total_coin_process3 = total_coin_process3 + 1
        prev_time_stamp_process3 = current_time_stamp_process3


        candle_datetime = datetime.fromtimestamp( msg['k']['t'] / 1e3 )

        #####################################################
        curr_open = float(msg['k']['o'])
        curr_high = float(msg['k']['h'])
        curr_low = float(msg['k']['l'])
        curr_closing = float(msg['k']['c'])

        # calculate % change for given time frame
        if len( process3_candle_dict_1m[ msg['s'] ] ) >= 1 :
            prev_closing = process3_candle_dict_1m[ msg['s'] ][-1][ Kline_data.C ]
            chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
            chg = int( chg*100 )
        else:
            chg = 0

        amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
        amp = int( amp*100 )

        process3_candle_dict_1m[ msg['s'] ].append( (candle_datetime, \
                                                   msg['k']['t'], \
                                                   curr_open, \
                                                   curr_high, \
                                                   curr_low, \
                                                   curr_closing, \
                                                   float( msg['k']['v'] ), \
                                                   msg['k']['i'],\
                                                   chg ,\
                                                   amp ) )

#        with open("candle_details.txt", "a") as file1:
#            file1.write(str(process3_candle_dict_1m[ msg['s'] ][-1]) + "\n")

        if chg > change_pc_thresold or amp > amp_pc_thresold:
            threading.Thread( target = generate_alert, \
              args = ( msg['s'], process3_candle_dict_1m[ msg['s'] ][-1] ) ,\
              daemon = True ).start()


        ####################################################
        # check if 3 minutes have passed
        if ( candle_datetime.minute + 1 ) % 3 == 0:
            # Let say worst situation is 1 2 | 2 X X
            if len(process3_candle_dict_1m[ msg['s']] ) > 3:
                # now we will use last 3 entries to calculate a candle

                curr_open = process3_candle_dict_1m[ msg['s']][-3][ Kline_data.O ]
                curr_closing = process3_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                         process3_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                         process3_candle_dict_1m[ msg['s']][-3][ Kline_data.H ] ])

                curr_low = min( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                         process3_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                         process3_candle_dict_1m[ msg['s']][-3][ Kline_data.L ] ])

                total_volume = sum( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                             process3_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                             process3_candle_dict_1m[ msg['s']][-3][ Kline_data.V] ])

                # calculate % change for given time frame
                if len( process3_candle_dict_3m[ msg['s'] ] ) >= 1 :
                    prev_closing = process3_candle_dict_3m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )

                process3_candle_dict_3m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=2),\
                                                          msg['k']['t'] - 2*60*1000,\
                                                          curr_open , \
                                                          curr_high ,\
                                                          curr_low ,\
                                                          curr_closing, \
                                                          total_volume ,\
                                                          "3m",\
                                                          chg,\
                                                          amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process3_candle_dict_3m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process3_candle_dict_3m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

        #####################################################
        # check if 5 minutes have passed
        if ( candle_datetime.minute + 1 ) % 5 == 0:
            if len(process3_candle_dict_1m[ msg['s']]) > 5:

                curr_open = process3_candle_dict_1m[ msg['s']][-5][ Kline_data.O ]

                curr_closing = process3_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                                  process3_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                                  process3_candle_dict_1m[ msg['s']][-3][ Kline_data.H ],\
                                  process3_candle_dict_1m[ msg['s']][-4][ Kline_data.H ],\
                                  process3_candle_dict_1m[ msg['s']][-5][ Kline_data.H ] ] )

                curr_low = min( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                                  process3_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                                  process3_candle_dict_1m[ msg['s']][-3][ Kline_data.L ],\
                                  process3_candle_dict_1m[ msg['s']][-4][ Kline_data.L ],\
                                  process3_candle_dict_1m[ msg['s']][-5][ Kline_data.L ] ] )

                total_volume = sum( [ process3_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                                      process3_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                                      process3_candle_dict_1m[ msg['s']][-3][ Kline_data.V ],\
                                      process3_candle_dict_1m[ msg['s']][-4][ Kline_data.V ],\
                                      process3_candle_dict_1m[ msg['s']][-5][ Kline_data.V ] ] )

                # calculate % change for given time frame
                if len( process3_candle_dict_5m[ msg['s'] ] ) >= 1 :
                    prev_closing = process3_candle_dict_5m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )


                # now we will use last 5 entries to calculate a candle
                process3_candle_dict_5m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=4),\
                                         msg['k']['t'] - 4*60*1000,\
                                         curr_open,\
                                         curr_high ,\
                                         curr_low ,\
                                         curr_closing,\
                                         total_volume ,\
                                         "5m",\
                                         chg,\
                                         amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process3_candle_dict_5m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process3_candle_dict_5m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

def process_message4(msg):

    global process4_candle_dict_1m
    global process4_candle_dict_3m
    global process4_candle_dict_5m

    global current_time_stamp_process4
    global prev_time_stamp_process4
    global total_coin_process4

    if msg['e'] == 'kline' and msg['k']['x'] == True:

        # code to understand start of messages
        current_time_stamp_process4 = int( round(time.time() * 1000) )
        diff_time_stamp = current_time_stamp_process4 - prev_time_stamp_process4

        if prev_time_stamp_process4 != 0 and diff_time_stamp > 15000 :
            #rootLogger.info("total coin last minute : " + str(total_coin_process4))
            total_coin_process4 = 0
            #threading.Thread( target = background_process_awake, daemon = True ).start()

        #rootLogger.info( "diff " + str( diff_time_stamp ))
        total_coin_process4 = total_coin_process4 + 1
        prev_time_stamp_process4 = current_time_stamp_process4


        candle_datetime = datetime.fromtimestamp( msg['k']['t'] / 1e3 )

        #####################################################
        curr_open = float(msg['k']['o'])
        curr_high = float(msg['k']['h'])
        curr_low = float(msg['k']['l'])
        curr_closing = float(msg['k']['c'])

        # calculate % change for given time frame
        if len( process4_candle_dict_1m[ msg['s'] ] ) >= 1 :
            prev_closing = process4_candle_dict_1m[ msg['s'] ][-1][ Kline_data.C ]
            chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
            chg = int( chg*100 )
        else:
            chg = 0

        amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
        amp = int( amp*100 )

        process4_candle_dict_1m[ msg['s'] ].append( (candle_datetime, \
                                                   msg['k']['t'], \
                                                   curr_open, \
                                                   curr_high, \
                                                   curr_low, \
                                                   curr_closing, \
                                                   float( msg['k']['v'] ), \
                                                   msg['k']['i'],\
                                                   chg ,\
                                                   amp ) )

#        with open("candle_details.txt", "a") as file1:
#            file1.write(str(process4_candle_dict_1m[ msg['s'] ][-1]) + "\n")

        if chg > change_pc_thresold or amp > amp_pc_thresold:
            threading.Thread( target = generate_alert, \
              args = ( msg['s'], process4_candle_dict_1m[ msg['s'] ][-1] ) ,\
              daemon = True ).start()


        ####################################################
        # check if 3 minutes have passed
        if ( candle_datetime.minute + 1 ) % 3 == 0:
            # Let say worst situation is 1 2 | 2 X X
            if len(process4_candle_dict_1m[ msg['s']] ) > 3:
                # now we will use last 3 entries to calculate a candle

                curr_open = process4_candle_dict_1m[ msg['s']][-3][ Kline_data.O ]
                curr_closing = process4_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                         process4_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                         process4_candle_dict_1m[ msg['s']][-3][ Kline_data.H ] ])

                curr_low = min( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                         process4_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                         process4_candle_dict_1m[ msg['s']][-3][ Kline_data.L ] ])

                total_volume = sum( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                             process4_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                             process4_candle_dict_1m[ msg['s']][-3][ Kline_data.V] ])

                # calculate % change for given time frame
                if len( process4_candle_dict_3m[ msg['s'] ] ) >= 1 :
                    prev_closing = process4_candle_dict_3m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )

                process4_candle_dict_3m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=2),\
                                                          msg['k']['t'] - 2*60*1000,\
                                                          curr_open , \
                                                          curr_high ,\
                                                          curr_low ,\
                                                          curr_closing, \
                                                          total_volume ,\
                                                          "3m",\
                                                          chg,\
                                                          amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process4_candle_dict_3m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process4_candle_dict_3m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

        #####################################################
        # check if 5 minutes have passed
        if ( candle_datetime.minute + 1 ) % 5 == 0:
            if len(process4_candle_dict_1m[ msg['s']]) > 5:

                curr_open = process4_candle_dict_1m[ msg['s']][-5][ Kline_data.O ]

                curr_closing = process4_candle_dict_1m[ msg['s']][-1][ Kline_data.C ]

                curr_high = max( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.H ],\
                                  process4_candle_dict_1m[ msg['s']][-2][ Kline_data.H ],\
                                  process4_candle_dict_1m[ msg['s']][-3][ Kline_data.H ],\
                                  process4_candle_dict_1m[ msg['s']][-4][ Kline_data.H ],\
                                  process4_candle_dict_1m[ msg['s']][-5][ Kline_data.H ] ] )

                curr_low = min( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.L ],\
                                  process4_candle_dict_1m[ msg['s']][-2][ Kline_data.L ],\
                                  process4_candle_dict_1m[ msg['s']][-3][ Kline_data.L ],\
                                  process4_candle_dict_1m[ msg['s']][-4][ Kline_data.L ],\
                                  process4_candle_dict_1m[ msg['s']][-5][ Kline_data.L ] ] )

                total_volume = sum( [ process4_candle_dict_1m[ msg['s']][-1][ Kline_data.V ],\
                                      process4_candle_dict_1m[ msg['s']][-2][ Kline_data.V ],\
                                      process4_candle_dict_1m[ msg['s']][-3][ Kline_data.V ],\
                                      process4_candle_dict_1m[ msg['s']][-4][ Kline_data.V ],\
                                      process4_candle_dict_1m[ msg['s']][-5][ Kline_data.V ] ] )

                # calculate % change for given time frame
                if len( process4_candle_dict_5m[ msg['s'] ] ) >= 1 :
                    prev_closing = process4_candle_dict_5m[ msg['s']][-1][ Kline_data.C ]
                    chg = round ( ( curr_closing -  prev_closing ) * 100/ prev_closing , 2 )
                    chg = int( chg*100 )
                else:
                    chg = 0

                amp = round ( ( curr_high -  curr_low ) * 100 / curr_open , 2 )
                amp = int( amp*100 )


                # now we will use last 5 entries to calculate a candle
                process4_candle_dict_5m[ msg['s'] ].append( ( candle_datetime - timedelta(minutes=4),\
                                         msg['k']['t'] - 4*60*1000,\
                                         curr_open,\
                                         curr_high ,\
                                         curr_low ,\
                                         curr_closing,\
                                         total_volume ,\
                                         "5m",\
                                         chg,\
                                         amp) )

#                with open("candle_details.txt", "a") as file1:
#                    file1.write(str(process4_candle_dict_5m[ msg['s'] ][-1]) + "\n")

                if chg > change_pc_thresold or amp > amp_pc_thresold:
                    threading.Thread( target = generate_alert, \
                      args = ( msg['s'], process4_candle_dict_5m[ msg['s'] ][-1] ) ,\
                      daemon = True ).start()

def store_coin_list_in_csv( coin_list, base_curr ):

    coin_csv_dir = os.path.join(os.path.normpath(os.getcwd()), 'coin_list_dir')
    Path(coin_csv_dir).mkdir(parents=True, exist_ok=True)

    time_format = "%Y_%m_%d_%H_%M_%S"
    time_now = datetime.now().date().strftime(time_format)
    csv_filename = "coin_list_" + base_curr + "_" + time_now  +".csv"

    csv_filepath = os.path.join( coin_csv_dir, csv_filename )

    with open(csv_filepath, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow([time_now])

        for coin in coin_list:
            csvwriter.writerow([coin])

    rootLogger.info("list stored in csv")

def start_tcp_socket_server():
    # this TCP server receives message from other processes like :
    # dummy trades and telegram forground.
    threading.Thread( target = tcp_server_thread, \
          args = () ,\
          daemon = True ).start()

def start_main_process():

    global process1_candle_dict_1m
    global process2_candle_dict_1m
    global process3_candle_dict_1m
    global process4_candle_dict_1m

    global process1_candle_dict_3m
    global process2_candle_dict_3m
    global process3_candle_dict_3m
    global process4_candle_dict_3m

    global process1_candle_dict_5m
    global process2_candle_dict_5m
    global process3_candle_dict_5m
    global process4_candle_dict_5m

    global bm

    set_client_BINANCE()
    #set_client_CCXT()
    set_client_TWITTER()
    set_client_Telegram()

    welcome_str = "Well come to our crypto sniffer bot , for any query contact @TradingMan101"
    send_telegram_msg_to_all(welcome_str)

    start_tcp_socket_server()

    # read all the BTC pairs and start the socket connection
    BTC_pairs = get_all_market_for_given_base_BINANCE( TRADE_BASE_CURRENCY )
    BTC_pairs.sort()

    total_BTC_pair = len( BTC_pairs )
    part = int( total_BTC_pair / 4 )

    # daily we will store coins in csv so that we can analyse coins daily.
    rootLogger.info("script start time : " + str(datetime.now()))
    rootLogger.info("total BTCPAIRS sent by binance: " + str(total_BTC_pair))
    store_coin_list_in_csv( BTC_pairs, TRADE_BASE_CURRENCY )

    bm = BinanceSocketManager(client_BINANCE)

    # each 1m , 3m and 5m candle will be in circular queue.
#    rootLogger.info(client_BINANCE.get_ticker(symbol='BNBBTC'))
#    conn_key = bm.start_kline_socket( "BNBBTC" , process_message1, interval = KLINE_INTERVAL_1MINUTE)
#    process1_candle_dict_1m["BNBBTC"] = collections.deque(maxlen=30)
#    process1_candle_dict_3m["BNBBTC"] = collections.deque(maxlen=30)
#    process1_candle_dict_5m["BNBBTC"] = collections.deque(maxlen=30)

    for i in range(0,part) :
        conn_key = bm.start_kline_socket( BTC_pairs[i] , process_message1, interval = KLINE_INTERVAL_1MINUTE)
        process1_candle_dict_1m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process1_candle_dict_3m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process1_candle_dict_5m[ BTC_pairs[i] ] = collections.deque(maxlen=30)

    for i in range(part , 2*part ) :
        conn_key = bm.start_kline_socket( BTC_pairs[i] , process_message2, interval = KLINE_INTERVAL_1MINUTE)
        process2_candle_dict_1m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process2_candle_dict_3m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process2_candle_dict_5m[ BTC_pairs[i] ] = collections.deque(maxlen=30)

    for i in range(2*part  , 3*part  ):
        conn_key = bm.start_kline_socket( BTC_pairs[i] , process_message3, interval = KLINE_INTERVAL_1MINUTE)
        process3_candle_dict_1m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process3_candle_dict_3m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process3_candle_dict_5m[ BTC_pairs[i] ] = collections.deque(maxlen=30)

    for i in range(3*part , len(BTC_pairs)) :
        conn_key = bm.start_kline_socket( BTC_pairs[i] , process_message4, interval = KLINE_INTERVAL_1MINUTE)
        process4_candle_dict_1m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process4_candle_dict_3m[ BTC_pairs[i] ] = collections.deque(maxlen=30)
        process4_candle_dict_5m[ BTC_pairs[i] ] = collections.deque(maxlen=30)

    bm.start()

    # now we will go in ideal loop.
    while True:
        sleep.sleep(5)
        time_now = datetime.now().time()
        if time_now > algo_end_time and time_now < algo_start_time:
            exit_script()


if __name__ == '__main__':
    try:
        set_logger()
        start_main_process()
    except KeyboardInterrupt:
        exit_script()
    except:
        exit_script()
