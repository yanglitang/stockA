import threading
from datetime import timedelta, time, date
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
import datetime
import copy
import requests
import json

from data import AStockTable, StockTable, Base, dbSession, dbEngine, get_model

global_header = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept':'*/*',
    'Accept-Encoding':'gzip, deflate, br'
}
global_url='https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={}&num={}&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=sort'

global_stock_url='https://stockapi.com.cn/v1/base2/secondHistory?date={}&code={}'

def print_function_name(func):
    def wrapper(*args, **kwargs):
        print('function name: ', func.__name__)
        return func(*args, **kwargs)
    return wrapper

class StocksDB:
    def __init__(self):
        self.listFocusStocks = []
        self.listSelStockRecords = []
        self.mutex = threading.RLock()
        self.filterShoushu = 0
        self.highLightShoushu = -1
        self.panQian = True
        self.panQianTime = time(9, 25, 0)
        self.dbPath = None

    def create(self, dbpath):
        global dbSession
        self.dbPath = dbpath
        dbURI='sqlite:///'+dbpath+'?charset=utf8'
        if not dbSession:
            dbEngine=create_engine(dbURI, echo=True)
            Session = sessionmaker(bind=dbEngine)
            dbSession=Session()
            Base.metadata.create_all(dbEngine)
            dbSession.commit()

    def getStockRTData(self):
        self.mutex.acquire()
        ret = copy.copy(self.listSelStockRecords)
        self.mutex.release()
        return ret

    def getStockRTDataCnt(self):
        self.mutex.acquire()
        ret = len(self.listSelStockRecords)
        self.mutex.release()
        return ret

    def setPanQian(self, panqian):
        self.panQian = panqian

    def getPanQian(self):
        return self.panQian

    def __updateFocusStocksFromDB(self):
        global dbSession
        self.mutex.acquire()
        stocks=dbSession.query(StockTable).all()
        self.listFocusStocks = [stock.to_dict() for stock in stocks]
        self.mutex.release()

    def loadFocusStocks(self):
        global dbSession
        global dbEngine
        focus_list = []
        self.mutex.acquire()
        print(self.dbPath)
        if self.dbPath:
            try:
                dbURI='sqlite:///'+self.dbPath+'?charset=utf8'
                if not dbSession:
                    dbEngine=create_engine(dbURI, echo=True)
                    Session = sessionmaker(bind=dbEngine)
                    dbSession=Session()
                    Base.metadata.create_all(dbEngine)
                    dbSession.commit()
                self.__updateFocusStocksFromDB()
            except Exception as e:
                print(f"Error opening database: {e}")
            focus_list = copy.copy(self.listFocusStocks)
        self.mutex.release()
        print(focus_list)
        return focus_list
    
    def reloadStockRTData(self, stock):
        global dbSession

        StockModel = get_model('stock_'+stock['code'])
        self.mutex.acquire()
        db_records = dbSession.query(StockModel).filter(StockModel.shoushu >= self.filterShoushu).order_by(StockModel.time.asc()).all()
        if self.panQian == True:
            self.stockRecordList = [record.to_dict() for record in db_records]
        else:
            self.stockRecordList.clear()
            for record in db_records:
                if record.time.time() >= self.panQianTime:
                    self.stockRecordList.append(record.to_dict())        
        self.mutex.release()

    def addFocusStocks(self, stock_data):
        global dbSession
        global dbEngine     
        insert = True   
        self.mutex.acquire()
        stocks=dbSession.query(StockTable).filter(StockTable.code==stock_data['code']).all()
        if len(stocks) <= 0:
            get_model('stock_'+stock_data['code'])
            Base.metadata.create_all(dbEngine)
            dbSession.add(StockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=(1970, 1, 1, 0, 0)))
            dbSession.commit()
            row=dbSession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            self.__updateFocusStocksFromDB()
            insert = True
        else:
            row=dbSession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            insert = False
        self.mutex.release()
        return (row.id, insert)
    
    def delFocusStocks(self, id):
        global dbSession     
        self.mutex.acquire()
        try:
            stock_table=Table(StockTable.__tablename__, Base.metadata, autoload=True)
            deleteQuery=stock_table.delete().where(stock_table.c.id==id)
            dbSession.execute(deleteQuery)
            dbSession.commit()
            self.__updateFocusStocksFromDB()
        except Exception as e:
            print(f"Error opening database: {e}")
        self.mutex.release()

    def updateFocusRealTimeHistory(self):
        self.mutex.acquire()
        focus_list = copy.copy(self.listFocusStocks)
        self.mutex.release()

        for stock in focus_list:
            self.updateStockRealTimeHistory(stock)

    def addRecord(self, stock, record):
        global dbEngine
        global dbSession

        self.mutex.acquire()
        StockModel = get_model('stock_' + stock['code'])
        date_format = "%Y-%m-%d %H:%M:%S"
        time = datetime.datetime.strptime(record['time'], date_format)
        rows = dbSession.query(StockModel).filter(StockModel.time == time).all()
        if len(rows) <= 0:
            dbSession.add(StockModel(time=time, price=float(record['price']), shoushu=int(record['shoushu']), bsbz=int(record['bsbz'])))
        self.mutex.release()

    def readFromWeb(self, url, stock):
        global dbSession
        response = requests.get(url, headers=global_header)
        if response.status_code == 200:
            response_data = response.json()
            if response_data["msg"] == 'success':
                for record in response_data['data']:
                    self.addRecord(stock, record)
                self.mutex.acquire()
                dbSession.commit()
                self.mutex.release()

    def updateFocusStockUpdateTime(self, stock, time):
        global dbSession
        self.mutex.acquire()
        dbSession.query(StockTable).filter(StockTable.code == stock['code']).update(StockTable.updateAt, time)
        self.mutex.release()

        self.__updateFocusStocksFromDB()

    def updateStockRealTimeHistory(self, stock):
        global dbSession
        global dbEngine

        self.mutex.acquire()
        StockModel = get_model('stock_'+stock['code'])
        Base.metadata.create_all(dbEngine)        
        latest_record = dbSession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        self.mutex.release()

        readfromweb = True
        latest_datetime = None
        if latest_record:
            time = latest_record.time
            if time.date() >= datetime.datetime.now().date():
                readfromweb = False
            latest_datetime = time
        if readfromweb:
            ten_days_ago = datetime.datetime.now() - timedelta(days=10)
            if not latest_datetime or latest_datetime < ten_days_ago:
                latest_datetime = datetime.datetime.now() - timedelta(days=11)
            while True:
                latest_datetime = latest_datetime + timedelta(days=1)
                format_latest_datetime = latest_datetime
                datestr = format_latest_datetime.strftime('%Y-%m-%d')
                url = global_stock_url.format(datestr, stock['code'])
                self.readFromWeb(url, stock)
                print(latest_datetime)
                if latest_datetime.date() >= datetime.datetime.now().date():
                    break

        self.mutex.acquire()
        StockModel = get_model('stock_'+stock['code']) 
        latest_record = dbSession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        if latest_record:
            self.updateFocusStockUpdateTime(stock, latest_record.time)
        self.mutex.release()

