# -*- coding: utf-8 -*-
"""
Created on Wed Oct 28 22:30:44 2020

@author: I20035

usage:
A second argument must be a JSON serialise dict.
example : 
          python binance_dummy_trade.py { "pair" : "BNBBTC", 
                                          "id": "ddsfsfdfs" , 
                                          "entry" : 0.0023080,  # use 0 for market orders or specify the price
                                          "TP" : 0.0023099,     # can be "abs" or "pc"
                                          "SL" : 0.0023070      # can be "abs" or "pc"
                                          "target_type" : "pc"  # <pc> for percentage and <abs> for absolute 
                                          "order_type" : "SLM"  # SLM for limit with upper value trigger
                                          }                     # L for limit with lower value trigger

tm_id = subprocess.Popen(["python","binance_dummy_trade.py",{ "pair" : "BNBBTC", id: "ddsfsfdfs" , "entry" : 0.0023080, "TP" : 0.0023099, "SL" : 0.0023070 } ])
you can keep entry_price 0 if you want market orders.

"order_type":
"SLM" = will take entry when the coin price crosses above your entry price.
"L" = will take entry when the coin price cross below your entry price.

"""

from binance.client import Client
from binance.websockets import BinanceSocketManager
import sys
import _thread
import time as sleep
from twisted.internet import reactor
import socket
import json
import logging
import os
from datetime import datetime
import threading
from pathlib import Path

sleep_time_sec = 5
kill_time_if_no_entry_sec = 15*60
kill_time_if_entry_but_no_trade_sec = 60*60
total_time = 0

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [p%(process)s] [%(levelname)-5.5s] {%(filename)s:%(lineno)d} %(message)s")
rootLogger = logging.getLogger()

#consoleHandler = logging.StreamHandler(sys.stdout)
#consoleHandler.setFormatter(logFormatter)
#rootLogger.addHandler(consoleHandler)

rootLogger.setLevel(level=logging.DEBUG)

client_BINANCE = None
trade_details = None
entry_taken = False
price = None

conn_key = None
bm = None

price_lock = threading.Lock()
exit_lock = threading.Lock()
last_data_sent = False


#dict1 = { "pair" : "BNBNTC" , "ID" : "dsdafadfsds" , "result" : "SL" , "entry" : 128.3 , "exit" : 120.4 }
#send_data_to_broadcast_thread(json.dumps(dict1))
def send_data_to_broadcast_thread( input_data ):
    
    received = b"0"
    HOST, PORT = "localhost", 9991
    
    # Create a socket (SOCK_STREAM means a TCP socket)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Connect to server and send data
            sock.connect((HOST, PORT))
            sock.sendall( input_data.encode(encoding='UTF-8') )
        
            # Receive data from the server and shut down
            sock.settimeout(2.0)
            received = sock.recv(1024)
        except Exception as e:
            pass
            rootLogger.exception( "exception in socket module : " + str(e) )
        finally:
            sock.close()
        
    except Exception as e:
        rootLogger.exception( "exception in socket module : " + str(e) )
        return received
    finally:
        if received is not None:
            return str( received, "utf-8")
        else:
            return received

def exit_trade():

    global trade_details
    global last_data_sent
    
    # send trade details to socket server before exiting.
    if last_data_sent == False:
        
        if trade_details["results"] == "NA":
        
            price_lock.acquire()
            trade_details["results_Price"] = price
            price_lock.release()
            
            if trade_details["results_Price"]  > trade_details["entry"]:
                trade_details["results"] = "TIMEOUT_TRADE_TP"
                rootLogger.info(trade_details)
            elif trade_details["results_Price"]  < trade_details["entry"]:
                trade_details["results"] = "TIMEOUT_TRADE_SL"
                rootLogger.info(trade_details)
        
        trade_dict_json = json.dumps( {"src":"dummy_trade", "payload" : trade_details } )
        send_data_to_broadcast_thread( trade_dict_json )
        last_data_sent = True
    
    rootLogger.info("closing this script")
    sleep.sleep(2)
    bm.close()
    reactor.stop()
    
    sleep.sleep(2)
    _thread.interrupt_main()
    os._exit(0)

def set_client_BINANCE():
    
    global client_BINANCE
    client_BINANCE = Client("kmqYFcd3ArdkKSpNjX0X6UJvrPnmnEvE6v0ibCJGpiOijVA4bhLPqdjlM9VNWnig",\
                            "hDJX0GJGbQSaLGISaWK4vs9Fx5aQLj3xFk4jUGz5VmSv74tCf2XqU4ct3ROPZe6u")
    
def process_message(msg):

    global price
    global price_lock
    global entry_taken
    global trade_details

    try:
        if msg['e'] == "trade" and msg['s'] == trade_details["pair"]:
            
            rootLogger.info("symbol: " + str(msg['s']) + " price : " + str(msg['p']))
            
            price_lock.acquire()
            price = float( msg['p'] )
            price_lock.release()
            
            if trade_details["entry"] == 0 and not entry_taken:
                
                trade_details["entry"] = price
                if trade_details["target_type"] == "pc":
                    
                    trade_details["TP"] =  trade_details["entry"] + \
                                          ( ( trade_details["TP"] * trade_details["entry"] ) / 100.0 )
                    trade_details["SL"] =  trade_details["entry"] - \
                                          ( ( trade_details["SL"] * trade_details["entry"] ) / 100.0 )
                                          
                    trade_details["TP"] = round( trade_details["TP"] , 8 )
                    trade_details["SL"] = round( trade_details["SL"] , 8 )
                    
                    entry_taken = True
                    rootLogger.info(trade_details)
                    
            elif not entry_taken and trade_details["order_type"] == "SLM":
                
                if price >= trade_details["entry"] :
                    trade_details["entry"] = price
                    entry_taken = True
                    rootLogger.info(trade_details)
                    
            elif not entry_taken and trade_details["order_type"] == "L":
                
                if price <= trade_details["entry"] :
                    trade_details["entry"] = price
                    entry_taken = True
                    rootLogger.info(trade_details)
                
                       
            if entry_taken :
                
                if price >= trade_details["TP"]:
                    trade_details["results"] = "TP"
                    trade_details["results_Price"] = price
                    rootLogger.info("TP hit at : " + str(msg['p']))
                    
                    exit_lock.acquire()
                    exit_trade()
                    exit_lock.release()
                    
                elif price <= trade_details["SL"]:
                    
                    trade_details["results"] = "SL"
                    trade_details["results_Price"] = price
                    rootLogger.info("SL hit at : " + str(msg['p']) )
                    
                    exit_lock.acquire()
                    exit_trade()
                    exit_lock.release()
            
    except Exception as e:
        rootLogger.exception( "exception in binance socket : " + str(e) )
        
        exit_lock.acquire()
        exit_trade()
        exit_lock.release()

def start_dummy_trade():
    
    global trade_details
    
    global conn_key
    global bm
    global total_time
    
    global price
    global price_lock
    global entry_taken
    
    param_list = sys.argv[1:]
    
    if len(param_list) >= 1:
        
        trade_details = json.loads(param_list[0])
        
        # add this 2 details for result of this trade.
        trade_details["results"] = "NA"
        trade_details["results_Price"] = "NA"
        
        # set logging details.
        log_dir = os.path.join(os.path.normpath(os.getcwd()), 'dummy_trade_logs')
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        fileName = "log_" + os.path.basename(__file__).split(".")[0] + \
                    "_" + str(datetime.now().date()) + \
                    "_" + str(trade_details["id"]) + ".log"
        log_fname = os.path.join(log_dir, fileName)
        
        fileHandler = logging.FileHandler(log_fname)
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)
        
        # if entry price is abosulute( not market ) and targets are provided with percentage.
        if trade_details["entry"] != 0 and trade_details["target_type"] == "pc":            
            if isinstance( trade_details["TP"], float) and isinstance( trade_details["SL"], float):
                trade_details["TP"] =  trade_details["entry"] + ( ( trade_details["TP"] * trade_details["entry"] ) / 100.0 )
                trade_details["SL"] =  trade_details["entry"] - ( ( trade_details["SL"] * trade_details["entry"] ) / 100.0 )
                
                trade_details["TP"] = round( trade_details["TP"] , 8 )
                trade_details["SL"] = round( trade_details["SL"] , 8 )
            else:
                raise Exception("Either TP or SL is not float type , even if target_type is percentage")
                
        rootLogger.info(trade_details)
    else:
        rootLogger.info("Not enough parameters to start dummy trade")
        return
    
    bm = BinanceSocketManager(client_BINANCE)
    conn_key = bm.start_trade_socket( trade_details["pair"], process_message)
    bm.start()
    
    rootLogger.info("while loop started !")
    
    while True:
        sleep.sleep(sleep_time_sec)
        total_time = total_time + sleep_time_sec
        
        if not entry_taken and ( total_time > kill_time_if_no_entry_sec ):
            
            trade_details["results"] = "TIMEOUT_NO_ENTRY"
            trade_details["results_Price"] = 0
            raise Exception("No entry Timeout occured !")
            
        if entry_taken and ( total_time > kill_time_if_entry_but_no_trade_sec ):
        
            price_lock.acquire()
            trade_details["results_Price"] = price
            price_lock.release()
            
            if trade_details["results_Price"]  > trade_details["entry"]:
                trade_details["results"] = "TIMEOUT_TRADE_TP"
                rootLogger.info(trade_details)
                raise Exception("No trade timeout occured !")
            elif trade_details["results_Price"]  < trade_details["entry"]:
                trade_details["results"] = "TIMEOUT_TRADE_SL"
                rootLogger.info(trade_details)
                raise Exception("No trade timeout occured !")

if __name__ == '__main__':
    try:
        start_dummy_trade()
    except Exception as e:
        rootLogger.exception( "exception in main thread : " + str(e) )
        
        exit_lock.acquire()
        exit_trade()
        exit_lock.release()
    except (KeyboardInterrupt, SystemExit):
        
        rootLogger.exception( "keyboard inturrupt or sys exit")
        
        exit_lock.acquire()
        exit_trade()
        exit_lock.release()        
    except :
        rootLogger.exception( "exception in main thread")
        
        exit_lock.acquire()
        exit_trade()
        exit_lock.release()