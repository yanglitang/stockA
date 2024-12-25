import threading
from datetime import timedelta, time, date
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
import datetime
import copy
import requests
import json

from data import AStockTable, StockTable, Base, get_model
from data import g_header, g_sina_stock_list_url, g_stockapi_rthistory_url

def print_function_name(func):
    def wrapper(*args, **kwargs):
        print('function name: ', func.__name__)
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
        self.dbPath = None

    def create(self, dbpath):
        self.dbPath = dbpath
        dbURI='sqlite:///'+dbpath+'?charset=utf8'
        if not StocksDB.s_dbsession:
            StocksDB.s_dbengine=create_engine(dbURI, echo=True)
            Session = sessionmaker(bind=StocksDB.s_dbengine)
            StocksDB.s_dbsession=Session()
            Base.metadata.create_all(StocksDB.s_dbengine)
            StocksDB.s_dbsession.commit()

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
        # self.lock.acquire()
        # # print(self.dbPath)
        # if self.dbPath:
        try:
            # dbURI='sqlite:///'+self.dbPath+'?charset=utf8'
            # if not StocksDB.s_dbsession:
            #     StocksDB.s_dbengine=create_engine(dbURI, echo=True)
            #     Session = sessionmaker(bind=StocksDB.s_dbengine)
            #     StocksDB.s_dbsession=Session()
            #     Base.metadata.create_all(StocksDB.s_dbengine)
            #     StocksDB.s_dbsession.commit()
            self.__updateFocusStocksFromDB()
        except Exception as e:
            print(f"Error opening database: {e}")
        focus_list = copy.copy(self.listFocusStocks)
        # self.lock.release()
        # print(focus_list)
        return focus_list
    
    def getDBAstocks(self):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).all()
        stock_list = [db_stock.to_dict() for db_stock in db_stocks]
        self.lock.release()
        return stock_list
    
    def getAStocks(self):
        stock_list = self.getDBAstocks()
        if(len(stock_list)):
            return stock_list
        else:
            stocks_cnt = 0
            for i in range(1, 10000):
                num = 80
                url=g_sina_stock_list_url.format(i, num)
                response = requests.get(url, headers=g_header)
                if response.status_code == 200:
                    response_data = response.json()
                    for stock_data in response_data:
                        self.addAStock(stock_data)
                        stocks_cnt = stocks_cnt + 1
                    if len(response_data) < num:
                        break
                else:
                    print('请求失败, 状态码: {}'.format(response.status_code))
                    break 
        stock_list = self.getDBAstocks()
        return stock_list
    
    def getAStockAlike(self, value):
        stock_list = []
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(or_(AStockTable.code.like('%'+value+'%'), AStockTable.name.like('%'+value+'%'))).all()
        if len(db_stocks) > 0:
            stock_list = [db_stock.to_dict() for db_stock in db_stocks]
        self.lock.release()
        return stock_list
    
    def addAstock(self, stock_data):
        self.lock.acquire()
        db_stocks = StocksDB.s_dbsession.query(AStockTable).filter(AStockTable.code == stock_data['code']).all()
        if len(db_stocks) <= 0:
            StocksDB.s_dbsession.add(AStockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=datetime.datetime.now()))
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

    def addFocusStocks(self, stock_data):
        insert = True   
        self.lock.acquire()
        stocks=StocksDB.s_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).all()
        if len(stocks) <= 0:
            get_model('stock_'+stock_data['code'])
            Base.metadata.create_all(StocksDB.s_dbengine)
            StocksDB.s_dbsession.add(StockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=datetime.datetime(1970, 1, 1, 0, 0, 0)))
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
            StocksDB.s_dbsession.add(StockModel(time=time, price=float(record['price']), shoushu=int(record['shoushu']), bsbz=int(record['bsbz'])))
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

    def __updateStockRT(self, stock, response_data):
        if(response_data['data'] and response_data['data']['details']):
            record_list = response_data['data']['details']
            for record_str in record_list:
                record = {}
                split_record = record_str.split(',')
                real_date = None
                if(datetime.datetime.now().time() < self.panQianTime):
                    real_date = datetime.datetime.now().date() - timedelta(days=1)
                else:
                    real_date = datetime.datetime.now().date()              
                record['time'] = real_date.strftime('%Y-%m-%d') + ' ' + split_record[0]
                record['price'] = split_record[1]
                record['shoushu'] = split_record[2]
                record['bsbz'] = split_record[4]
                self.addRecord(stock, record)
            self.lock.acquire()
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

        readfromweb, latest_datetime = self.isReadFromWeb(stock)
        if(readfromweb):
            url = f'https://16.push2.eastmoney.com/api/qt/stock/details/sse?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55&mpi=2000&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&pos=-0&secid={mcode}.{stock['code']}&wbp2u=|0|0|0|web'
            with requests.get(url, headers=g_header, stream=True) as response:
                for line in response.iter_lines():
                    if line and line.startswith(b'data:'):
                        data_str = line[5:].decode('utf-8')
                        response = json.loads(data_str)
                        self.__updateStockRT(stock, response)
                        break

    def updateAStockRT(self):
        stock_list = self.getAStocks()
        for stock in stock_list:
            self.updateStockRT(stock)

    def updateFocusStockUpdateTime(self, stock, time):
        self.lock.acquire()
        StocksDB.s_dbsession.query(StockTable).filter(StockTable.code == stock['code']).update({StockTable.updateAt: time})
        self.lock.release()

        self.__updateFocusStocksFromDB()

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
            if time.date() >= datetime.datetime.now().date():
                readfromweb = False
            latest_datetime = time

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
                print(latest_datetime)
                if latest_datetime.date() >= datetime.datetime.now().date():
                    break

        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code']) 
        latest_record = StocksDB.s_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        if latest_record:
            self.updateFocusStockUpdateTime(stock, latest_record.time)
        self.lock.release()

