
import logging
import logging.config
import configparser

g_mainwnd = None
g_logger = None
g_config = None

def get_mainwnd():
    global g_mainwnd
    return g_mainwnd

def set_mainwnd(wnd):
    global g_mainwnd
    g_mainwnd = wnd

def init_logger(config_path):
    global g_logger
    logging.config.fileConfig(config_path)
    g_logger = logging.getLogger()

def get_logger():
    global g_logger
    return g_logger

def init_default_configuration():
    global g_config
    g_config['Database'] = {
        'host': 'localhost',
        'port': '5432',
        'user': 'username',
        'password': 'secret',
        'database': 'dbname'
    }

def init_config(config_path):
    global g_config
    g_config = configparser.ConfigParser()
    init_default_configuration()
    g_config.read(config_path)

def get_config():
    global g_config
    return g_config
