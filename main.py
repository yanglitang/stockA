from apscheduler.schedulers.background import BackgroundScheduler
from stocksDB import StocksDB
import time
import argparse
from GlobalInstance import init_logger, get_logger, init_config, get_config
import datetime

stocks_db = StocksDB()

def update_stockrt_from_internet():
    stocks_db.updateAStockRT()

def update_astock_from_internet():
    stocks_db.updateAStock()

def create_database():
    #初始化数据库引擎
    stocks_db.createPG()
    #将所有存储股票逐笔成交数据的数据表创建出来
    # stocks_db.createAllRTTable()

def start_update_db():
    create_database()
    config = get_config()
    update_db_scheduler = BackgroundScheduler()

    #每次程序启动时，更新一下股票列表
    # update_astock_from_internet()
    astock_trigger_time = datetime.time(0, 0, 5)
    if(config.get('Update', 'astock_trigger') == 'cron'):
        astock_trigger_time = datetime.datetime.strptime(config.get('Update', 'astock_trigger_cron'), '%H:%M:%S').time()
    #程序开始运行后，根据设定的更新规则，更新股票列表
    update_db_scheduler.add_job(update_astock_from_internet, \
                                'cron', \
                                    hour=astock_trigger_time.hour, \
                                        minute=astock_trigger_time.minute, \
                                            second=astock_trigger_time.second)
    
    #根据设定的规则，定期更新股票的逐笔成交数据
    update_db_scheduler.add_job(update_stockrt_from_internet, \
                                config.get('Update', 'rt_trigger'), \
                                    seconds=int(config.get('Update', 'rt_trigger_interval').strip()), \
                                        coalesce=True, \
                                            max_instances=int(config.get('Update', 'max_instances').strip()))
    update_db_scheduler.start()

if __name__ == '__main__':
    usage = '[-c | --config] config'
    description = 'web crawler collect stock data'
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument('--config', '-c', help='config file path')
    args = parser.parse_args()
    if(not args.config):
        print(usage)
        exit(1)
    
    config_path = args.config
    init_logger(config_path)
    get_logger().info('============================================')
    get_logger().info('============================================')
    get_logger().info('=================service start==============')
    
    init_config(config_path)
    stocks_db.initialize()

    start_update_db()
    while(True):
        time.sleep(1)
