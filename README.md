# Sniffer Bot :

This bot scans multiple pairs on binance exchange and see price movement in terms of change and amplitude for more than 2% on 1m, 3m , 5m candles.
when such incident occurs it will check twitter account timelines for that coin.
if there is twitt made in short span say 15 min , then this bot will send notification on telegram.
It also generates dummy trade with SL and TP , to check validity of detected signals.
It also holds files for creating twitter data base.

It's availible on telegram at : @Cryptosnifferbot_bot

=================================================

### Setting up your environment for development :

1. First install virtuale env : pip install virtualenv. ( use virtualenv --version to see if virualenv is installed ).
2. Use python -V to see version. We need python 3 for our project. If you do not have python 3 , then install from here : https://www.python.org/downloads/mac-osx/.
3. Find the path for python3 installation in Mac : /Library/Frameworks/Python.framework/Versions/3.9/Python.bin. ( https://stackoverflow.com/questions/6767283/find-where-python-is-installed-if-it-isnt-default-dir ).
4. Intiliasing virtualenv with python3 : virtualenv -p python3 <desired-path>.
5. create a virtual env with python3 ( specify your python3 path ): virtualenv --python="C:\Users\a0490374\AppData\Local\Programs\Python\Python39\python.exe" sniffer_env.
6. activate that virtualenv : .\sniffer_env\Scripts\activate **( for mac => source sniffer_env/bin/activate )**: https://gist.github.com/Geoyi/d9fab4f609e9f75941946be45000632b )
7. r.txt is availible in repo : pip install -r r.txt
8. Now on 2 seperate shells ( cmd on windows ) run these 2 files :
   - **python binance_data_fetch.py**
   - **python sniffer_bot_main_telegram_process.py**
6. deactivate that virtualenv : .\sniffer_env\Scripts\deactivate **( for mac => deactivate )**


command list for mac users : https://support.apple.com/en-in/guide/mac-help/cpmh0152/mac.

=================================================

### Understanding Project structure :

there is mainly 3 file which is used while running bot, 2 files needed to be triggered by user ( sniffer_bot_main_telegram_process.py and binance_data_fetch.py ) and  1 file ( binance_dummy_trade.py ) is used internally :

1) **sniffer_bot_main_telegram_process.py**
- This file is responsible for user management in the bot.
- It identify telegram commands like /addme, /removeme, /myhealth, /start.
- It also send socket messages to **binance_data_fetch.py** , to update it's user database in real time.

2) **binance_data_fetch.py**
- This is the main file which do all data processing on candles and twitter data.
- It also triggers binance_dummy_trade.py when signal is detected.
- It also sends telegram messages about detected signal to all registered users.
- It listen on socket from sniffer_bot_main_telegram_process.py and binance_dummy_trade.py.
- It fetch data from binance and then check twitts.

3) **binance_dummy_trade.py**
- This file is triggered in different shell , to generat the dummy trade.
- Mainly binance_data_fetch.py triggers this file and generate dummy_trade.

note : read comment headers in individual file for more info.

=================================================

### Database

all data is stored in .json format and currently there is no DBMS is used.

1) coin_twitterDB_SymbolAsKey.json
- hold information about twitter id and twitter accounts of each coin.

2) user_list_sniffer_bot.json
- holds information about user of the bot. Auto created on checked in.

=================================================

### Fetching data from coinmarketcap and creating twitter data base.

we use coin market cap to get twitter account details.
We need to refreash our coin list and twitter account time 2 time.

following steps need to be followed :
1) first upto date data from cmc is needed : run cmc_data_fetch.py file , this will create CMC_Coin_Details_Auto_*.xls file
2) copy content of this file to : coin_comparision_twitter_accounts_cmc.xls.
3) using coin_comparision_twitter_accounts_cmc.xls find out which coins are added to binance, we don't worry about which coins are removed. just find added coins and their twitter ids.
4) add this new data to : list_of_twitter_accounts.csv. remember we always do incremental changes.
5) finanly run : generate_twitterAcc_json_from_csv.py
6) this will generate : coin_twitter_acc_db_symbolAsKey.json


=================================================

### Usefull Info :

1) To create r.txt file : pip freeze > r.txt
2) To kill all running python shells : pkill -9 python

=================================================

### Important Points :

1) it's been noticed and identified that this code have issues while running on linux based system and using nested threding and network call. code runs fine on windows 10 system.
