def extract_mcode(stockcode):
    mcode = '0'
    if(stockcode[0] == '3' or \
        stockcode[0] == '0' or \
        stockcode[0] == '4' or \
        stockcode[0] == '8' or \
            stockcode[0] == '9'):
        mcode = '0'
    elif(stockcode[0] == '6'):
        mcode = '1'
    return mcode