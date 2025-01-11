import psycopg
import threading
from datetime import timedelta, time, date
from sqlalchemy import create_engine, Table, or_, inspect
from sqlalchemy.orm import sessionmaker
import datetime
import copy
import requests
import json

from data import AStockTable, StockTable, Base, get_model, get_hday_model
from data import g_header, g_sina_stock_list_url, g_stockapi_rthistory_url

from urllib.parse import quote_plus
from trade_calendar import get_previous_tradeday, sse_is_tradeday

from GlobalInstance import get_logger,  get_config
from utils import extract_mcode

import threading
import gzip
import brotli
import brotlicffi

def print_function_name(func):
    def wrapper(*args, **kwargs):
        get_logger().debug(f'function name: {func.__name__}')
        return func(*args, **kwargs)
    return wrapper

class StocksDB:
    s_dbsession = None
    s_dbengine = None
    def __init__(self):
        self.listFocusStocks = []
        self.listSelStockRecords = []
        self.lock = threading.RLock()
        self.filterShoushu = 0
        self.highLightShoushu = -1
        self.panQian = True
        self.panQianTime = time(9, 25, 0)
        self.panHouTime = time(15, 0, 0)
        self.dbPath = None

    def initialize(self):
        config = get_config()
        self.panQianTime = datetime.datetime.strptime(config.get('AShares', 'PreMarket'), '%H:%M:%S').time()
        self.panHouTime = datetime.datetime.strptime(config.get('AShares', 'AHT'), '%H:%M:%S').time()

    def create(self, dbpath):
        self.dbPath = dbpath
        dbURI='sqlite:///'+dbpath+'?charset=utf8'
        if not StocksDB.s_dbsession:
            StocksDB.s_dbengine=create_engine(dbURI, echo=True)
            Session = sessionmaker(bind=StocksDB.s_dbengine)
            StocksDB.s_dbsession=Session()
            Base.metadata.create_all(StocksDB.s_dbengine)
            StocksDB.s_dbsession.commit()

    def createPG(self):
        config = get_config()
        pwd = quote_plus(config.get('Database', 'password').strip())
        dbURI=(f"postgresql+psycopg://{config.get('Database', 'user')}:{pwd}"
               f"@{config.get('Database', 'host')}:{config.get('Database', 'port')}"
               f"/{config.get('Database', 'db')}")
        get_logger().info(f'dburi: {dbURI}')
        if not StocksDB.s_dbsession:
            StocksDB.s_dbengine=create_engine(dbURI, echo=False)
            Session = sessionmaker(bind=StocksDB.s_dbengine)
            StocksDB.s_dbsession=Session()
            Base.metadata.create_all(StocksDB.s_dbengine)
            StocksDB.s_dbsession.commit()
        get_logger().info(f'initialize database suscceed,'
                          f'host: {config.get('Database', 'host')},'
                          f'database: {config.get('Database', 'db')}')

    def getStockRTData(self):
        self.lock.acquire()
        ret = copy.copy(self.listSelStockRecords)
        self.lock.release()
        return ret

    def getStockRTDataCnt(self):
        self.lock.acquire()
        ret = len(self.listSelStockRecords)
        self.lock.release()
        return ret
    
    def setShoushu(self, shoushu):
        self.filterShoushu = shoushu

    def getShoushu(self):
        return self.filterShoushu

    def setPanQian(self, panqian):
        self.panQian = panqian

    def getPanQian(self):
        return self.panQian

    def __updateFocusStocksFromDB(self):
        self.lock.acquire()
        stocks=StocksDB.s_dbsession.query(StockTable).all()
        self.listFocusStocks = [stock.to_dict() for stock in stocks]
        self.lock.release()

    def loadFocusStocks(self):
        focus_list = []
        try:
            self.__updateFocusStocksFromDB()
        except Exception as e:
            get_logger().error(f'opening database failed, error: {e}')
        focus_list = copy.copy(self.listFocusStocks)
        return focus_list
    
    def getDBAstocks(self):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).all()
        stock_list = [db_stock.to_dict() for db_stock in db_stocks]
        self.lock.release()
        return stock_list
    
    def getAStocks(self):
        return self.getDBAstocks()
    
    def getAStockAlike(self, value):
        stock_list = []
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(or_(AStockTable.code.like('%'+value+'%'), AStockTable.name.like('%'+value+'%'))).all()
        if len(db_stocks) > 0:
            stock_list = [db_stock.to_dict() for db_stock in db_stocks]
        self.lock.release()
        return stock_list
    
    def addAStock(self, stock_data):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock_data['code']).all()
        if len(db_stocks) <= 0:
            get_logger().info(f'add new stock to astock, '
                              f'stock code: {stock_data['code']}, '
                              f'stock name: {stock_data['name']}')
            StockModel = get_model('stock_'+stock_data['code'])
            inspector = inspect(self.s_dbengine)
            if not inspector.has_table('stock_'+stock_data['code']):
                get_logger().info(f'create table for stock, '
                                f'stock code: {stock_data['code']}, '
                                f'stock name: {stock_data['name']}')
                StockModel.__table__.create(self.s_dbengine)
            StocksDB.s_dbsession.add(AStockTable(code=stock_data['code'], \
                                                 name=stock_data['name'], \
                                                    createAt=datetime.datetime.now(), \
                                                        updateAt=datetime.datetime.now(), \
                                                            state='ready'))
            StocksDB.s_dbsession.commit()
        self.lock.release()
    
    def getStock(self, code):
        self.lock.acquire()
        for stock in self.listFocusStocks:
            if(stock['code'] == code):
                self.lock.release()
                return stock
        self.lock.release()
        return None
    
    def reloadStockRTData(self, stock):
        StockModel = get_model('stock_'+stock['code'])
        self.lock.acquire()
        db_records = StocksDB.s_dbsession.query(StockModel).filter(StockModel.shoushu >= self.filterShoushu).order_by(StockModel.time.asc()).all()
        if self.panQian == True:
            self.listSelStockRecords = [record.to_dict() for record in db_records]
        else:
            self.listSelStockRecords.clear()
            for record in db_records:
                if record.time.time() >= self.panQianTime:
                    self.listSelStockRecords.append(record.to_dict())        
        self.lock.release()

    def getLatestUpdateTime(self, stock):
        latest_update_time = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code']) 
        latest_record = StocksDB.s_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        if latest_record:
            latest_update_time = latest_record.time
        self.lock.release()
        return latest_update_time  

    def addFocusStocks(self, stock_data):
        insert = True   
        self.lock.acquire()
        stocks=StocksDB.s_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).all()
        if len(stocks) <= 0:
            get_model('stock_'+stock_data['code'])
            Base.metadata.create_all(StocksDB.s_dbengine)
            update_time = self.getLatestUpdateTime(stock_data)
            StocksDB.s_dbsession.add(StockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=update_time))
            StocksDB.s_dbsession.commit()
            row=StocksDB.s_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            self.__updateFocusStocksFromDB()
            insert = True
        else:
            row=StocksDB.s_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            insert = False
        self.lock.release()
        return (row.id, insert)
    
    def delFocusStocks(self, id):
        self.lock.acquire()
        try:
            stock_table=Table(StockTable.__tablename__, Base.metadata, autoload=True)
            deleteQuery=stock_table.delete().where(stock_table.c.id==id)
            StocksDB.s_dbsession.execute(deleteQuery)
            StocksDB.s_dbsession.commit()
            self.__updateFocusStocksFromDB()
        except Exception as e:
            get_logger().error(f'opening database failed, error: {e}')
            print(f"Error opening database: {e}")
        self.lock.release()

    def updateFocusRealTimeHistory(self):
        self.lock.acquire()
        focus_list = copy.copy(self.listFocusStocks)
        self.lock.release()

        for stock in focus_list:
            self.updateStockRealTimeHistory(stock)

    def addRecord(self, stock, record):
        self.lock.acquire()
        StockModel = get_model('stock_' + stock['code'])
        date_format = "%Y-%m-%d %H:%M:%S"
        time = datetime.datetime.strptime(record['time'], date_format)
        rows = StocksDB.s_dbsession.query(StockModel).filter(StockModel.time == time).all()
        if len(rows) <= 0:
            StocksDB.s_dbsession.add(StockModel(time=time, price=float(record['price']), shoushu=int(record['shoushu']), danshu=int(record['danshu']), bsbz=int(record['bsbz'])))
        self.lock.release()

    def readFromWeb(self, url, stock):
        response = requests.get(url, headers=g_header)
        if response.status_code == 200:
            response_data = response.json()
            if response_data["msg"] == 'success':
                for record in response_data['data']:
                    self.addRecord(stock, record)
                self.lock.acquire()
                StocksDB.s_dbsession.commit()
                self.lock.release()

    def createAllRTTable(self):
        stock_list = self.getAStocks()
        self.lock.acquire()
        for stock in stock_list:
            get_model('stock_'+stock['code'])
        Base.metadata.create_all(StocksDB.s_dbengine)
        self.lock.release()

    def __updateStockRT(self, stock, response_data, update_date):
        ret = False
        if(response_data['data'] and response_data['data']['details']):
            get_logger().debug(f'update database, code {stock['code']}')
            record_list = response_data['data']['details']
            for record_str in record_list:
                record = {}
                split_record = record_str.split(',')     
                record['time'] = update_date.strftime('%Y-%m-%d') + ' ' + split_record[0]
                record['price'] = split_record[1]
                record['shoushu'] = split_record[2]
                record['danshu'] = split_record[3]
                record['bsbz'] = split_record[4]
                self.addRecord(stock, record)
                ret = True
            self.lock.acquire()
            StocksDB.s_dbsession.commit()
            self.lock.release()
        return ret

    def startStockUpdating(self, stock):
        ret = False
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).all()
        if(len(db_stocks) > 0):
            if(db_stocks[0].state != 'ready'):
                ret = False
            else:
                get_logger().debug(f'start updating stock, stock: {stock['code']}')
                StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).update({AStockTable.state: 'updating'})
                ret =  True

        StockModel = get_model('stock_'+stock['code'])
        inspector = inspect(self.s_dbengine)
        if not inspector.has_table('stock_'+stock['code']):
            StockModel.__table__.create(self.s_dbengine)

        StocksDB.s_dbsession.commit()
        self.lock.release()
        return ret
    
    def stopStockUpdating(self, stock):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).all()
        if(len(db_stocks) > 0):
            if(db_stocks[0].state == 'updating'):
                get_logger().debug(f'stop updating stock, stock: {stock['code']}')
                StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).update({AStockTable.state: 'ready'})
        StocksDB.s_dbsession.commit()
        self.lock.release()

    def updateStockRT(self, stock):
        mcode = '0'
        if(stock['code'][0] == '3' or \
           stock['code'][0] == '0' or \
           stock['code'][0] == '4' or \
            stock['code'][0] == '8' or \
                stock['code'][0] == '9'):
            mcode = '0'
        elif(stock['code'][0] == '6'):
            mcode = '1'

        canupdate = self.startStockUpdating(stock)
        if(not canupdate):
            get_logger().debug(f'cannot update stock, stock code: {stock['code']}')
            return
        
        readfromweb, latest_datetime = self.isReadFromWeb(stock)
        if(readfromweb):
            url = f'https://16.push2.eastmoney.com/api/qt/stock/details/sse?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55&mpi=2000&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&pos=-0&secid={mcode}.{stock['code']}&wbp2u=|0|0|0|web'
            get_logger().info(f'read stock rtdata from internet, code{stock['code']}, url: {url}')
            with requests.get(url, headers=g_header, stream=True) as response:
                time_now = datetime.datetime.now()
                update_date = time_now.date()
                if(sse_is_tradeday(time_now.date())):
                    if(time_now.time() < self.panQianTime):
                        update_date = get_previous_tradeday(time_now.date())
                    else:
                        update_date = time_now.date()
                else:
                    update_date = get_previous_tradeday(time_now.date())
                iterate_cnt = 0
                for line in response.iter_lines():
                    if line and line.startswith(b'data:'):
                        data_str = line[5:].decode('utf-8')
                        response = json.loads(data_str)
                        self.__updateStockRT(stock, response, update_date)
                        break

                self.lock.acquire()
                StockModel = get_model('stock_'+stock['code']) 
                latest_record = StocksDB.s_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
                if latest_record:
                    self.updateFocusStockUpdateTime(stock, latest_record.time)
                    self.updateAStockUpdateTime(stock, latest_record.time)
                self.lock.release()
        self.stopStockUpdating(stock)

    def updateAStockRT(self):
        stock_list = self.getAStocks()
        updated = 0
        for stock in stock_list:
            self.updateStockRT(stock)
            updated = updated + 1
            if(updated % 100 == 0):
                get_logger().info(f'thread: {threading.current_thread().ident}, update stock: {stock['code']}, progress: {updated}/{len(stock_list)}')

    def updateAStock(self):
        stocks_cnt = 0
        for i in range(1, 10000):
            num = 80
            url=g_sina_stock_list_url.format(i, num)
            response = requests.get(url, headers=g_header)
            if response.status_code == 200:
                get_logger().debug(f'read stock list succeed, page num: {num}, url: {url}, error: {response.status_code}')
                response_data = response.json()
                for stock_data in response_data:
                    self.addAStock(stock_data)
                    stocks_cnt = stocks_cnt + 1
                if len(response_data) < num:
                    break
            else:
                get_logger().error(f'read stock list failed, url: {url}, error: {response.status_code}')
                break
        get_logger().info(f'update astock, stocks: {stocks_cnt}')

    def updateFocusStockUpdateTime(self, stock, time):
        self.lock.acquire()
        StocksDB.s_dbsession.query(StockTable).filter(StockTable.code == stock['code']).update({StockTable.updateAt: time})
        self.lock.release()

        self.__updateFocusStocksFromDB()

    def updateAStockUpdateTime(self, stock, time):
        self.lock.acquire()
        StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).update({AStockTable.updateAt: time})
        self.lock.release()

    def isReadFromWeb(self, stock):
        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code'])
        # Base.metadata.create_all(StocksDB.s_dbengine)        
        latest_record = StocksDB.s_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        self.lock.release()

        readfromweb = True
        latest_datetime = None
        if latest_record:
            time = latest_record.time
            if(time.time() < self.panHouTime):
                to_compare = datetime.datetime.now()
                if(sse_is_tradeday(to_compare.date())):
                    if(to_compare.time() >= self.panQianTime and to_compare.time() <= self.panHouTime):
                        get_logger().debug('miss data, trade time, won\'t read from web')
                        readfromweb = False
                    else:
                        get_logger().debug('miss data, trade day but not trade time, read from web')
                        readfromweb = True
                else:
                    get_logger().debug('miss data, not trade day, read from web')
                    readfromweb = True
            else:
                to_compare = datetime.datetime.now().date()
                if(not sse_is_tradeday(to_compare)):
                    to_compare = get_previous_tradeday(to_compare)
                    if(time.date() < to_compare):
                        get_logger().debug('not trade day, rtdata missing, read from web')
                        readfromweb = True
                    else:
                        get_logger().debug('not trade day, rtdata not missing, won\'t read from web')
                        readfromweb = False
                else:
                    if(datetime.datetime.now().time() >= self.panQianTime\
                        and datetime.datetime.now().time() <= self.panHouTime):
                        get_logger().debug('trade day, trade time, won\'t read from web')
                        readfromweb = False
                    else:
                        if(datetime.datetime.now().time() < self.panQianTime):
                            to_compare = get_previous_tradeday(to_compare)
                        if(time.date() < to_compare):
                            get_logger().debug('trade day, not trade time, rtdata missing, read from web')
                            readfromweb = True
                        else:
                            get_logger().debug('trade day, not trade time, rtdata not missing, won\'t read from web')
                            readfromweb = False
            latest_datetime = time
        else:
            readfromweb = True
            to_compare = datetime.datetime.now()
            if(sse_is_tradeday(to_compare.date())):
                if(to_compare.time() >= self.panQianTime and to_compare.time() <= self.panHouTime):
                    get_logger().debug('trade day, trade time, won\'t read from web')
                    readfromweb = False
                else:
                    get_logger().debug('no rtdata in database, not trade time, read from web')
            else:
                get_logger().debug('no rtdata in database, not trade time, read from web')
            latest_datetime = datetime.datetime(1970,1,1,0,0,0)

        return readfromweb, latest_datetime

    def updateStockRealTimeHistory(self, stock):
        readfromweb, latest_datetime = self.isReadFromWeb(stock)
        if readfromweb:
            ten_days_ago = datetime.datetime.now() - timedelta(days=10)
            if not latest_datetime or latest_datetime < ten_days_ago:
                latest_datetime = datetime.datetime.now() - timedelta(days=11)
            while True:
                latest_datetime = latest_datetime + timedelta(days=1)
                format_latest_datetime = latest_datetime
                datestr = format_latest_datetime.strftime('%Y-%m-%d')
                url = g_stockapi_rthistory_url.format(datestr, stock['code'])
                self.readFromWeb(url, stock)
                if latest_datetime.date() >= datetime.datetime.now().date():
                    break

        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code']) 
        latest_record = StocksDB.s_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        if latest_record:
            self.updateFocusStockUpdateTime(stock, latest_record.time)
        self.lock.release()

    def isPreMarketTime(self, time):
        return time >= datetime.time(0, 0, 0) and time <= self.panQianTime
    
    def isAHT(self, time):
        return time >= self.panHouTime and time <= datetime.time(23, 59, 59)

    def startHDayUpdating(self, stock):
        ret = False
        retdatetime = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).all()
        if(len(db_stocks) > 0):
            retdatetime = db_stocks[0].hdayUpdate
            if(db_stocks[0].hdayState != 'ready'):
                ret = False
            else:
                get_logger().debug(f'start updating hday, stock: {stock['code']}')
                StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock['code']).update({AStockTable.hdayState: 'updating'})
                ret =  True

        StockModel = get_hday_model('stock_hday_'+stock['code'])
        inspector = inspect(self.s_dbengine)
        if not inspector.has_table('stock_hday_'+stock['code']):
            StockModel.__table__.create(self.s_dbengine)

        StocksDB.s_dbsession.commit()
        self.lock.release()
        return ret, retdatetime
    
    def stopHDayUpdating(self, stock):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable)\
            .filter(AStockTable.code == stock['code']).all()
        if(len(db_stocks) > 0):
            if(db_stocks[0].hdayState == 'updating'):
                get_logger().debug(f'stop updating hday, stock: {stock['code']}')
                StocksDB.s_dbsession.query(AStockTable)\
                    .filter(AStockTable.code == stock['code'])\
                        .update({AStockTable.hdayState: 'ready'})
        StocksDB.s_dbsession.commit()
        self.lock.release()

    def appendHDayIncrementData(self, stock, records):
        self.lock.acquire()
        StockModel = get_hday_model('stock_hday_' + stock['code'])
        rows = StocksDB.s_dbsession.query(StockModel.time).order_by(StockModel.time.desc()).all()
        db_updatetime = datetime.datetime(1970, 1, 1, 0, 0, 0)
        if len(rows) > 0:
            db_updatetime = rows[0]
        for line in records:
            parts = line.split(',')
            record_time = datetime.datetime.strptime(parts[0], '%Y-%m-%d')
            if(record_time > db_updatetime):
                StocksDB.s_dbsession.add(StockModel(time=record_time, \
                                                    kaipan = float(parts[1]), \
                                                    shoupan = float(parts[2]), \
                                                    zuigao = float(parts[3]), \
                                                    zuidi = float(parts[4]), \
                                                    volumn = float(parts[5]), \
                                                    ammount = float(parts[6]), \
                                                    zhenfu = float(parts[7]), \
                                                    zhangdiefu = float(parts[8]), \
                                                    zhangdie = float(parts[9]), \
                                                    huanshou = float(parts[10])))
        StocksDB.s_dbsession.commit()
        self.lock.release()

    def updateAStockHDayUpdateTime(self, stock, date):
        self.lock.acquire()
        updatetime = datetime.datetime(date.year, date.month, date.day, 15, 0, 0)
        StocksDB.s_dbsession.query(AStockTable)\
            .filter(AStockTable.code == stock['code'])\
                .update({AStockTable.hdayUpdate: updatetime})
        self.lock.release()

    def updateStockAllHistoryHDayData(self, stock, starttime, endtime):
        mcode = extract_mcode(stock['code'])
        url = (f'http://push2his.eastmoney.com/api/qt/stock/kline/get?fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13'
        f'&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
        f'&beg={starttime.strftime('%Y%m%d')}&end={endtime.strftime('%Y%m%d')}&ut=fa5fd1943c7b386f172d6893dbfba10b&rtntype=6'
        f'&secid={mcode}.{stock['code']}&klt=101&fqt=1&cb=jsonp1736601605163')
        
        get_logger().info(f'read stock hday from internet, code{stock['code']}, url: {url}')

        updated = False
        response = requests.get(url, headers=g_header, stream=True)
        if(response.status_code == 200):
            decoded_text = '\{\}'
            if 'charset' in response.headers.get('Content-Type', ''):
                response.encoding = response.headers['Content-Type'].split('charset=')[-1]
            else:
                response.encoding = 'utf-8'

            if response.headers.get('content-encoding') == 'gzip':
                # 解压 gzip 内容
                # import io
                # gzip_file = gzip.GzipFile(fileobj=io.BytesIO(response.content))
                # decoded_text = gzip_file.read()
                decoded_text = response.content.decode(response.encoding)
            elif response.headers.get('content-encoding') == 'br':
                responsedata = response.raw.read()
                decoded_text = brotlicffi.decompress(responsedata).decode(response.encoding)
            else:
                decoded_text = response.text

            if(decoded_text.find('(') != -1 \
               and decoded_text.rfind(')') != -1 \
                and decoded_text.rfind(')') > decoded_text.find('(')):
                retjson = json.loads(decoded_text[decoded_text.find('(') + 1:decoded_text.rfind(')')])
                if(retjson['data'] and retjson['data']['klines']):
                    lines = retjson['data']['klines']
                    get_logger().debug(f'lines count: {len(lines)}')
                    self.appendHDayIncrementData(stock, lines)
                    updated = True
        if(updated):
            timenow = datetime.datetime.now()
            if(self.isPreMarketTime(timenow.time())\
               or not sse_is_tradeday(timenow.date())):
                self.updateAStockHDayUpdateTime(stock, get_previous_tradeday(timenow.date()))
            elif(self.isAHT(timenow.time())):
                self.updateAStockHDayUpdateTime(stock, timenow.date())

    def updateHDayData(self, stock):
        canupdate, hday_updateat = self.startHDayUpdating(stock)
        if(not canupdate):
            get_logger().debug(f'cannot update stock hday, stock code: {stock['code']}')
            return
        timenow = datetime.datetime.now()
        while(True):
            #盘前时间，发现更新的数据大于前一个交易日的数据，不用更新
            if(self.isPreMarketTime(timenow.time()) \
               and hday_updateat.date() >= get_previous_tradeday(timenow.date())):
                break

            #盘后时间，发现更新的数据已经大于当天的日期，不用更新数据
            if(self.isAHT(timenow.time()) \
               and hday_updateat.date() >= timenow.date()):
                break

            #交易日的交易时间段不更新数据
            if(sse_is_tradeday(timenow.date())\
               and not self.isPreMarketTime(timenow.time())\
                and not self.isAHT(timenow.time())):
                break
            self.updateStockAllHistoryHDayData(stock, hday_updateat, datetime.datetime(2050, 1, 1, 0, 0))
            break
        self.stopHDayUpdating(stock)

    def updateHDay(self):
        stock_list = self.getAStocks()
        updated = 0
        for stock in stock_list:
            self.updateHDayData(stock)
            updated = updated + 1
            if(updated % 100 == 0):
                get_logger().info(f'thread: {threading.current_thread().ident}, update stock: {stock['code']}, progress: {updated}/{len(stock_list)}')



