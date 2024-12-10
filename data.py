from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

def to_dict(self):
    return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
  
Base.to_dict = to_dict

stock_class_dict = {}

class AStockTable(Base):
    __tablename__ = 'astock_table'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code=Column(String)
    name=Column(String)
    createAt=Column(DateTime)
    updateAt=Column(DateTime)

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
    bsbz = Column(Integer)
    
def get_model(tablename):
    Model = stock_class_dict.get(tablename, None)
    if Model is None:
        Model = type(tablename, (StockRealTimeHistory, ), {
            '__tablename__': tablename
        })
        stock_class_dict[tablename] = Model
    return Model

dbSession=None
dbEngine=None
