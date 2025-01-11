from apscheduler.schedulers.background import BackgroundScheduler
from stocksDB import StocksDB
import time
import argparse
from GlobalInstance import init_logger, get_logger, init_config, get_config
import datetime

stocks_db = StocksDB()

def update_hday_from_internet():
    stocks_db.updateHDay()

def create_database():
    #初始化数据库引擎
    stocks_db.createPG()

def start_update_db():
    create_database()
    config = get_config()

    update_hday_from_internet()

    update_db_scheduler = BackgroundScheduler()
    #每次程序启动时，更新一下股票列表
    hday_trigger_time = datetime.time(0, 0, 5)
    if(config.get('Update', 'hday_trigger') == 'cron'):
        hday_trigger_time = datetime.datetime.strptime(config.get('Update', 'hday_trigger_cron'), '%H:%M:%S').time()
    #程序开始运行后，根据设定的更新规则，更新股票列表
    update_db_scheduler.add_job(update_hday_from_internet, \
                                'cron', \
                                    hour=hday_trigger_time.hour, \
                                        minute=hday_trigger_time.minute, \
                                            second=hday_trigger_time.second)
    update_db_scheduler.start()

if __name__ == '__main__':
    usage = '[-c | --config] config'
    description = 'web crawler collect stock history daily data'
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

