# Sniffer Bot :

This bot scans multiple pairs on binance exchange and see price movement for more than 2% on 1m, 3m , 5m.
when such incident occurs it will check twitter account for that coin.
if there is twitt made in short span say 5 min , then this bot will notify on telegram.
It also generates dummy trade to check validity of detected signals.
It also holds files for creating twitter data base.

It's availible on telegram at : @Cryptosnifferbot_bot

=================================================

### Setting up environment for development :

1. first install virtuale env : pip install virtualenv. ( use virtualenv --version to see if virualenv is installed ).
2. Use python -V to see version. We need python 3 for our project. If you do not have python 3 , then install from here : https://www.python.org/downloads/mac-osx/.
3. find the path for python3 installation in Mac : /Library/Frameworks/Python.framework/Versions/3.9/Python.bin. ( https://stackoverflow.com/questions/6767283/find-where-python-is-installed-if-it-isnt-default-dir ).
4. Intiliasing virtualenv with python3 : virtualenv -p python3 <desired-path>.
5. create a virtual env with python3 ( specify your python3 path ): virtualenv --python="C:\Users\a0490374\AppData\Local\Programs\Python\Python39\python.exe" sniffer_env.
6. activate that virtualenv : .\sniffer_env\Scripts\activate ( for mac => source sniffer_env/bin/activate ): https://gist.github.com/Geoyi/d9fab4f609e9f75941946be45000632b )
7. r.txt is availible in repo : pip install -r r.txt
8. on 2 seperate shells run this 2 files :
   python binance_data_fetch.py
   python sniffer_bot_main_telegram_process.py
6. deactivate that virtualenv : .\sniffer_env\Scripts\deactivate ( for mac => source sniffer_env/bin/deactivate )

=================================================

### Understanding Project structure :

there is mainly 3 file which runs the bot :

1) sniffer_bot_main_telegram_process.py
- this file is responsible for use management in the bot.
- it identify commands like /addme , /removeme.
- it also send socket message to binance_data_fetch.py , to make user registration real time.

2) binance_data_fetch.py
- this is the main file which do all data processing.
- it listen on socket from sniffer_bot_main_telegram_process.py,
- it fetch data from binance and then check twitts.

3) binance_dummy_trade.py
- this file is triggered in different shell , to generat the dummy trade.
- mainly binance_data_fetch.py triggers this file and generate dummy_trade.

=================================================

### database

all data is stored in .json format and currently there is no data base used.

1) coin_twitter_acc_db_symbolAsKey.json
- hold information about twitter id and twitter accounts of each coin.

2) user_list_sniffer_bot.json
- holds information about user of the bot.

=================================================

### fetching data from coinmarketcap and creating twitter data base.

we use coin market cap to get twitter account details.
We need to refreash our coin list and twitter account time 2 time.

following steps need to be followed :
1) run cmc_data_fetch.py file , this will create CMC_Coin_Details_Auto_*.xls.
2) now you need to manually identify coin pairs and create : coin_twitter_info.csv file
3) one can take help of coin_comparision_twitter_accounts_cmc.xls in this process.
4) finanly run : prepare_twitter_json_db_from_csv.py 
5) this will generate : coin_twitter_acc_db_symbolAsKey.json


=================================================

To create r.txt file : pip freeze > r.txt
