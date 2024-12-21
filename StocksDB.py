import threading
from datetime import timedelta, time, date
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
import datetime
import copy
import requests
import json

from data import AStockTable, StockTable, Base, g_dbsession, g_dbengine, get_model
from data import g_header, g_sina_stock_list_url, g_stockapi_rthistory_url

def print_function_name(func):
    def wrapper(*args, **kwargs):
        print('function name: ', func.__name__)
        return func(*args, **kwargs)
    return wrapper

class StocksDB:
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
        global g_dbsession
        self.dbPath = dbpath
        dbURI='sqlite:///'+dbpath+'?charset=utf8'
        if not g_dbsession:
            g_dbengine=create_engine(dbURI, echo=True)
            Session = sessionmaker(bind=g_dbengine)
            g_dbsession=Session()
            Base.metadata.create_all(g_dbengine)
            g_dbsession.commit()

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
        global g_dbsession
        self.lock.acquire()
        stocks=g_dbsession.query(StockTable).all()
        self.listFocusStocks = [stock.to_dict() for stock in stocks]
        self.lock.release()

    def loadFocusStocks(self):
        # global g_dbsession
        # global g_dbengine
        focus_list = []
        # self.lock.acquire()
        # # print(self.dbPath)
        # if self.dbPath:
        try:
            # dbURI='sqlite:///'+self.dbPath+'?charset=utf8'
            # if not g_dbsession:
            #     g_dbengine=create_engine(dbURI, echo=True)
            #     Session = sessionmaker(bind=g_dbengine)
            #     g_dbsession=Session()
            #     Base.metadata.create_all(g_dbengine)
            #     g_dbsession.commit()
            self.__updateFocusStocksFromDB()
        except Exception as e:
            print(f"Error opening database: {e}")
        focus_list = copy.copy(self.listFocusStocks)
        # self.lock.release()
        # print(focus_list)
        return focus_list
    
    def getStock(self, code):
        for stock in self.listFocusStocks:
            if(stock['code'] == code):
                return stock
        return None
    
    def reloadStockRTData(self, stock):
        global g_dbsession

        StockModel = get_model('stock_'+stock['code'])
        self.lock.acquire()
        db_records = g_dbsession.query(StockModel).filter(StockModel.shoushu >= self.filterShoushu).order_by(StockModel.time.asc()).all()
        if self.panQian == True:
            self.listSelStockRecords = [record.to_dict() for record in db_records]
        else:
            self.listSelStockRecords.clear()
            for record in db_records:
                if record.time.time() >= self.panQianTime:
                    self.listSelStockRecords.append(record.to_dict())        
        self.lock.release()

    def addFocusStocks(self, stock_data):
        global g_dbsession
        global g_dbengine     
        insert = True   
        self.lock.acquire()
        stocks=g_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).all()
        if len(stocks) <= 0:
            get_model('stock_'+stock_data['code'])
            Base.metadata.create_all(g_dbengine)
            g_dbsession.add(StockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=(1970, 1, 1, 0, 0)))
            g_dbsession.commit()
            row=g_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            self.__updateFocusStocksFromDB()
            insert = True
        else:
            row=g_dbsession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            insert = False
        self.lock.release()
        return (row.id, insert)
    
    def delFocusStocks(self, id):
        global g_dbsession     
        self.lock.acquire()
        try:
            stock_table=Table(StockTable.__tablename__, Base.metadata, autoload=True)
            deleteQuery=stock_table.delete().where(stock_table.c.id==id)
            g_dbsession.execute(deleteQuery)
            g_dbsession.commit()
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
        global g_dbengine
        global g_dbsession

        self.lock.acquire()
        StockModel = get_model('stock_' + stock['code'])
        date_format = "%Y-%m-%d %H:%M:%S"
        time = datetime.datetime.strptime(record['time'], date_format)
        rows = g_dbsession.query(StockModel).filter(StockModel.time == time).all()
        if len(rows) <= 0:
            g_dbsession.add(StockModel(time=time, price=float(record['price']), shoushu=int(record['shoushu']), bsbz=int(record['bsbz'])))
        self.lock.release()

    def readFromWeb(self, url, stock):
        global g_dbsession
        response = requests.get(url, headers=g_header)
        if response.status_code == 200:
            response_data = response.json()
            if response_data["msg"] == 'success':
                for record in response_data['data']:
                    self.addRecord(stock, record)
                self.lock.acquire()
                g_dbsession.commit()
                self.lock.release()

    def updateFocusStockUpdateTime(self, stock, time):
        global g_dbsession
        self.lock.acquire()
        g_dbsession.query(StockTable).filter(StockTable.code == stock['code']).update({StockTable.updateAt: time})
        self.lock.release()

        self.__updateFocusStocksFromDB()

    def updateStockRealTimeHistory(self, stock):
        global g_dbsession
        # global g_dbengine

        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code'])
        # Base.metadata.create_all(g_dbengine)        
        latest_record = g_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        self.lock.release()

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
                url = g_stockapi_rthistory_url.format(datestr, stock['code'])
                self.readFromWeb(url, stock)
                print(latest_datetime)
                if latest_datetime.date() >= datetime.datetime.now().date():
                    break

        self.lock.acquire()
        StockModel = get_model('stock_'+stock['code']) 
        latest_record = g_dbsession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
        if latest_record:
            self.updateFocusStockUpdateTime(stock, latest_record.time)
        self.lock.release()

