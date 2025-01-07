from apscheduler.schedulers.background import BackgroundScheduler
from stocksDB import StocksDB
import time

stocks_db = StocksDB()

def update_db_from_internet():
    stocks_db.updateAStockRT()

def create_database():
    stocks_db.createPG()
    stocks_db.createAllRTTable()

def start_update_db():
    create_database()
    update_db_task = BackgroundScheduler()
    update_db_task.add_job(update_db_from_internet, 'interval', seconds=5, coalesce=True, max_instances=1)
    update_db_task.start()    

if __name__ == '__main__':
    start_update_db()
    while(True):
        time.sleep(1)
