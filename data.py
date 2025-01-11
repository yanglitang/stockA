import psycopg
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

def to_dict(self):
    return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
  
Base.to_dict = to_dict

stock_class_dict = {}
hday_class_dict = {}

class AStockTable(Base):
    __tablename__ = 'astock_table'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code=Column(String)
    name=Column(String)
    createAt=Column(DateTime)
    updateAt=Column(DateTime)
    state=Column(String)
    hdayState=Column(String)
    hdayUpdate=Column(DateTime)

class StockTable(Base):
    __tablename__ = 'stock_table'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code=Column(String)
    name=Column(String)
    createAt=Column(DateTime)
    updateAt=Column(DateTime)

class StockRealTimeHistory(Base):
    __abstract__ =  True
    extend_existing = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime)
    price = Column(Float)
    shoushu = Column(Integer)
    danshu = Column(Integer)
    bsbz = Column(Integer)

class StockHDayHistory(Base):
    __abstract__ =  True
    extend_existing = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime)
    kaipan = Column(Float)
    shoupan = Column(Float)
    zuigao = Column(Float)
    zuidi = Column(Float)
    volumn = Column(Float)
    ammount = Column(Float)
    zhenfu = Column(Float)
    zhangdiefu = Column(Float)
    zhangdie = Column(Float)
    huanshou = Column(Float)
    
def get_model(tablename):
    global stock_class_dict
    Model = stock_class_dict.get(tablename, None)
    if Model is None:
        Model = type(tablename, (StockRealTimeHistory, ), {
            '__tablename__': tablename
        })
        stock_class_dict[tablename] = Model
    return Model

def get_hday_model(tablename):
    global hday_class_dict
    Model = hday_class_dict.get(tablename, None)
    if Model is None:
        Model = type(tablename, (StockHDayHistory, ), {
            '__tablename__': tablename
        })
        hday_class_dict[tablename] = Model
    return Model

g_header = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept':'*/*',
    'Accept-Encoding':'gzip'
}
g_sina_stock_list_url='https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={}&num={}&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=sort'
g_stockapi_rthistory_url='https://stockapi.com.cn/v1/base2/secondHistory?date={}&code={}'

