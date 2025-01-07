from chinese_calendar import is_workday
from trade_calendar_constants import __trade_calendar_constants
from datetime import timedelta

def sse_workday_not_tradeday(date):
    date_str = date.strftime("%Y-%m-%d")
    value = __trade_calendar_constants['sse_constants']['workday_not_tradeday'].get(date_str)
    if(value):
        return bool(value)
    else:
        return False

def sse_tradeday_not_workday(date):
    date_str = date.strftime("%Y-%m-%d")
    value = __trade_calendar_constants['sse_constants']['tradeday_not_workday'].get(date_str)
    if(value):
        return bool(value)
    else:
        return False

def sse_is_tradeday(date):
    if(is_workday(date) and not sse_workday_not_tradeday(date)):
        return True
    if(not is_workday(date) and sse_tradeday_not_workday(date)):
        return  True
    return False

def get_previous_tradeday(date):
    previous_date = date
    while(True):
        previous_date = previous_date - timedelta(1)
        if(sse_is_tradeday(previous_date)):
            return previous_date
        
def get_post_tradeday(date):
    post_date = date
    while(True):
        post_date = post_date + timedelta(1)
        if(sse_is_tradeday(post_date)):
            return post_date
        
