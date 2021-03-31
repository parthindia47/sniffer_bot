# -*- coding: utf-8 -*-
"""
Created on Sun Nov  1 00:12:56 2020

@author: I20035
"""

import json
import subprocess
import socketserver
import threading
import time as sleep


class MyTCPHandler(socketserver.BaseRequestHandler):
    # server must override the handle() method to implement communication to the client.

    def handle(self):
        
        global id_list_lock
        global CHAT_IDs
        # self.request is the TCP socket connected to the client
        data = self.request.recv(1024).strip()
        
        try:
            data = json.loads(data.decode(encoding='UTF-8'))
            print("Update from dummy trade")
            print(data)
        except:
            print("socket : not valid json")

def tcp_server_thread():
    
    HOST, PORT = "localhost", 9990

    # Create the server, binding to localhost on port 9999
    try:
        server = socketserver.TCPServer((HOST, PORT), MyTCPHandler)
        server.allow_reuse_address = True
        server.serve_forever()
    except Exception as e:
        print(e)
        return None

trade_dict = { "pair" : "BNBBTC", "id": "ddsfsfdfs" , "entry" : 0.0018384, "TP" : 10.0, "SL" : 10.0, "target_type" :  "pc", "order_type" : "SLM"}
#trade_dict = { "pair" : "BOTBTC", "id": "ddsfsfdfs" , "entry" : 0.02722, "TP" : 5, "SL" : 3, "target_type" :  "pc", "order_type" : "SLM"}
trade_dict_json = json.dumps(trade_dict)


threading.Thread( target = tcp_server_thread, \
      args = () ,\
      daemon = True ).start()

subp_id = subprocess.Popen( [ "python", "binance_dummy_trade.py", trade_dict_json ] )
print("waiting for subprocess to complete")
subp_id.wait()
print("subprocess complete")
sleep.sleep(5)
