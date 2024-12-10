import wx
import wx.grid
import wx.lib
import wx.lib.newevent
import xlrd
import sqlite3
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
from data import AStockTable, StockTable, Base, dbSession, dbEngine, get_model
import datetime
from datetime import timedelta, time, date
import requests
import json

(EventType, EVT_TRANS_DATA_EVENT) = wx.lib.newevent.NewEvent()

global_header = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept':'*/*',
    'Accept-Encoding':'gzip, deflate, br'
}
global_url='https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={}&num={}&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=sort'

global_stock_url='https://stockapi.com.cn/v1/base2/secondHistory?date={}&code={}'

class TransDataEvent(wx.PyCommandEvent):
    def __init__(self, data=None):
        wx.PyCommandEvent.__init__(self, EventType)
        self.data = data
 
    def GetData(self):
        return self.data

class SelStockWindow(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title)
        # 设置新窗口的布局和其他属性
        panel = wx.Panel(self)
        self.selStock = {}

        stockCntCtrl = wx.StaticText(panel, label='股票总数： 0')
        self.stockCodeCtrl=wx.TextCtrl(panel)
        self.stockCodeCtrl.SetSizeWH(20, -1)
        search_button = wx.Button(panel, -1, '搜索股票')
        self.Bind(wx.EVT_BUTTON, self.onSearchButton, search_button)
        self.stockList=wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.stockList.InsertColumn(0, '股票代码')
        self.stockList.InsertColumn(1, '股票名称')
        self.stockList.SetColumnWidth(0, 150)
        self.stockList.SetColumnWidth(1, 150)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onStockListDoubleClicked, self.stockList)

        global dbSession
        # atable=Table(AStockTable.__tablename__, Base.metadata)
        # sel_stmt=atable.select()
        query = dbSession.query(AStockTable)
        db_stocks=query.all()
        stockCntCtrl.SetLabelText('股票总数：%d'%(len(db_stocks)))
        if len(db_stocks) > 0:
            dict_rows=[row.to_dict() for row in db_stocks]
            for row in dict_rows:
                self.showStock(row)
        else:
            stocks_cnt = 0
            for i in range(1, 10000):
                num = 80
                url=global_url.format(i, num)
                print(url)
                response = requests.get(url, headers=global_header)
                if response.status_code == 200:
                    response_data = response.json()
                    for stock_data in response_data:
                        self.addStock(stock_data)
                        stocks_cnt = stocks_cnt + 1
                    if len(response_data) < num:
                        break
                else:
                    print('请求失败, 状态码: {}'.format(response.status_code))
                    break
            query = dbSession.query(AStockTable)
            db_stocks=query.all()
            stockCntCtrl.SetLabelText('股票总数：%d'%(len(db_stocks)))

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(stockCntCtrl, flag=wx.RIGHT | wx.ALIGN_BOTTOM, border=100)
        buttonSizer.Add(self.stockCodeCtrl, flag=wx.ALIGN_BOTTOM, border=10)
        buttonSizer.Add(search_button, flag=wx.ALIGN_BOTTOM, border=10)
        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(buttonSizer)
        panelSizer.Add(self.stockList, 1, wx.EXPAND)
        panel.SetSizer(panelSizer)
        self.Centre()
        self.Show()

    def OnClose(self, event):
        self.Destroy()

    def showStock(self, stock_data):
        index=self.stockList.InsertItem(0, stock_data['code'])
        self.stockList.SetItem(index, 1, stock_data['name'])

    def addStock(self, stock_data):
        global dbSession
        # atable=Table(AStockTable.__tablename__, Base.metadata)
        # sel_stmt=atable.select().where(atable.c.code == stock_data['code'])
        # db_stocks=dbSession.execute(sel_stmt)
        db_stocks = dbSession.query(AStockTable).filter(AStockTable.code == stock_data['code']).all()
        if len(db_stocks) <= 0:
            dbSession.add(AStockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=datetime.datetime.now()))
            dbSession.commit()
        self.showStock(stock_data)

    def onStockListDoubleClicked(self, event):
        index = event.GetIndex()
        self.selStock['code']=self.stockList.GetItemText(index, 0)
        self.selStock['name']=self.stockList.GetItemText(index, 1)
        self.Close()

    def onSearchButton(self, event):
        global dbSession
        search_text = self.stockCodeCtrl.GetValue().strip()
        if len(search_text) > 0:
            db_stocks = dbSession.query(AStockTable).filter(or_(AStockTable.code.like('%'+search_text+'%'), AStockTable.name.like('%'+search_text+'%'))).all()
            if len(db_stocks) > 0:
                self.stockList.DeleteAllItems()
                for row in db_stocks:
                    index = self.stockList.InsertItem(0, row.code)
                    self.stockList.SetItem(index, 1, row.name)

class MainWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Excel Import")
        self.panel = wx.Panel(self)

        self.selStock = {}
        self.stockRecordList = []
        self.showStart = -1
        self.showEnd = -1
        self.filterShoushu = 0
        self.panQian = True
        self.panQianTime = time(9, 25, 0)
        
        self.selWindow=None
        fileMenu=wx.Menu()
        fileMenuOpen=fileMenu.Append(-1,'打开','打开数据库')
        fileMenuExit=fileMenu.Append(-1,'退出','退出程序')
        menuBar=wx.MenuBar()
        menuBar.Append(fileMenu,'文件')
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.onFileChanged, fileMenuOpen)
        self.Bind(wx.EVT_MENU, self.onExit, fileMenuExit)
        self.Bind(wx.EVT_SIZE, self.OnSize)
   
        self.stockList=wx.ListCtrl(self.panel, style=wx.LC_REPORT)
        self.stockList.InsertColumn(0, '股票代码')
        self.stockList.InsertColumn(1, '股票名称')
        self.stockList.SetColumnWidth(0, 150)
        self.stockList.SetColumnWidth(1, 150)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onStockListSelected, self.stockList)
  
        addStockButton=wx.Button(self.panel, -1, '添加')
        self.Bind(wx.EVT_BUTTON, self.onAddStock, addStockButton)
        deleteStockButton=wx.Button(self.panel, -1, '删除')
        self.Bind(wx.EVT_BUTTON, self.onDeleteStock, deleteStockButton)

        self.filterShoushuCtrl =wx.TextCtrl(self.panel)
        self.filterShoushuCtrl.SetSizeWH(20, -1)
        filter_button = wx.Button(self.panel, -1, '过滤')
        self.Bind(wx.EVT_BUTTON, self.onFilterShoushuClicked, filter_button)

        self.filterPanQianCtrl = wx.CheckBox(self.panel, label='过滤盘前竞价')
        self.filterPanQianCtrl.Bind(wx.EVT_CHECKBOX, self.onfilterPanQianCtrl)

        self.grid = wx.grid.Grid(self.panel)
        self.createGrid()
        self.grid.Bind(wx.EVT_SCROLLWIN, self.onScrollWin)
        self.grid.Bind(wx.EVT_KEY_DOWN, self.onKey)
        # self.Bind(wx.EVT_SCROLL_LINEUP, self.onScrollUp, self.grid.GetVerticalScroller())
        # self.Bind(wx.EVT_SCROLL_BOTTOM, self.onScrollDown, self.grid.GetVerticalScroller())

        buttonSizer=wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(addStockButton)
        buttonSizer.Add(deleteStockButton)   
        listSizer=wx.BoxSizer(wx.VERTICAL)
 
        listSizer.Add(self.stockList, 1, wx.EXPAND, 5)
        listSizer.Add(buttonSizer, 0, wx.EXPAND, 5)   

        grid_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        grid_button_sizer.Add(self.filterShoushuCtrl)
        grid_button_sizer.Add(filter_button)
        grid_button_sizer.Add(self.filterPanQianCtrl)

        grid_sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer.Add(grid_button_sizer, 0, wx.EXPAND, 5)
        grid_sizer.Add(self.grid, 1, wx.EXPAND, 5)

        panelSizer=wx.BoxSizer(wx.HORIZONTAL)
        panelSizer.Add(listSizer, 0, wx.EXPAND)
        panelSizer.Add(grid_sizer, 1, wx.EXPAND)
        
        self.panel.SetSizer(panelSizer)

        self.Show()

    def loadData(self):
        global dbSession
        global dbEngine
        index = self.stockList.GetFirstSelected()
        if index >= 0:
            self.selStock['code'] = self.stockList.GetItemText(index, 0)
            self.selStock['name'] = self.stockList.GetItemText(index, 1)
            StockModel = get_model('stock_'+self.selStock['code'])
            db_records = dbSession.query(StockModel).filter(StockModel.shoushu >= self.filterShoushu).order_by(StockModel.time.asc()).all()
            if self.panQian == True:
                self.stockRecordList = [record.to_dict() for record in db_records]
            else:
                self.stockRecordList.clear()
                for record in db_records:
                    if record.time.time() >= self.panQianTime:
                        self.stockRecordList.append(record.to_dict())


    # def updateRecordList(self):
    #     global dbSession
    #     global dbEngine
    #     index = self.stockList.GetFirstSelected()
    #     if index >= 0:
    #         self.selStock['code'] = self.stockList.GetItemText(index, 0)
    #         self.selStock['name'] = self.stockList.GetItemText(index, 1)
    #         StockModel = get_model('stock_'+self.selStock['code'])
    #         db_records = dbSession.query(StockModel).filter(StockModel.shoushu >= self.filterShoushu).order_by(StockModel.time.asc()).all()
    #         self.stockRecordList = [record.to_dict() for record in db_records] 

    def onfilterPanQianCtrl(self, event):
        refill_grid = False
        if self.filterPanQianCtrl.GetValue():
            if(self.panQian == True):
                refill_grid =  True
                self.panQian = False
        else:
            if self.panQian == False:
                refill_grid = False
                self.panQian = True
        if refill_grid:
            self.loadData()
            self.fillGrid(self.stockRecordList)

    def onFilterShoushuClicked(self, event):
        filter_text = self.filterShoushuCtrl.GetValue().strip()
        if len(filter_text) > 0:
            self.filterShoushu = int(filter_text)
            self.loadData()
            self.fillGrid(self.stockRecordList)

    def onScrollWin(self, event):
        event_type = event.GetEventType()
        self.scrollGrid(event_type)
        if event:
            event.Skip()

    def scrollGrid(self, event_type):
        row_cnt = self.grid.GetNumberRows()
        if row_cnt <= 0:
            self.loadData()
        if len(self.stockRecordList) > 0:
            if self.grid.IsVisible(row_cnt - 1, 0) and (event_type == wx.EVT_SCROLL_LINEDOWN or event_type == wx.EVT_SCROLL_PAGEDOWN):
                if self.showEnd >= 0 and self.showEnd < len(self.stockRecordList):
                    # 获取滚动条位置
                    (x_pos, y_pos) = self.grid.GetScrollPos(wx.VERTICAL)
                    # 获取滚动条的最大范围
                    (x_max, y_max) = self.grid.GetScrollRange()
                    # 判断是否滚动到了底部
                    if y_pos + self.grid.GetClientSize()[1] >= y_max:                   
                        self.grid.AppendRows(5)
            if self.grid.IsVisible(0, 0) and (event_type == wx.EVT_SCROLL_LINEUP or event_type == wx.EVT_SCROLL_PAGEUP):
                if self.showStart > 0:
                    # 获取滚动条位置
                    y_pos = self.grid.GetScrollPos(wx.VERTICAL)
                    # 判断是否滚动到了顶部
                    if y_pos == 0:
                        expand_cnt = min(5, (self.showStart * 3)//self.grid.GetNumberCols())
                        self.grid.InsertRows(0, expand_cnt)
            self.fillGrid(self.stockRecordList)

    def onKey(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DOWN or keycode == wx.WXK_PAGEDOWN:
            self.scrollGrid(wx.EVT_SCROLL_LINEDOWN if keycode == wx.WXK_DOWN else wx.EVT_SCROLL_PAGEDOWN)
        if keycode == wx.WXK_UP or keycode == wx.WXK_PAGEUP:
            self.scrollGrid(wx.EVT_SCROLL_LINEUP if keycode == wx.WXK_UP else wx.EVT_SCROLL_PAGEUP)
        if event:
            event.Skip()

    def OnSize(self, event):
        self.expandGrid()
        event.Skip()

    def expandGrid(self):
        size = self.panel.GetSize()
        height = size[1]
        new_rows = max(1, height // self.grid.GetDefaultRowSize())
        old_rows = self.grid.GetNumberRows()
        if new_rows > old_rows:
            self.grid.AppendRows(new_rows - old_rows)

    def getTextColor(self, record):
        text_color = None
        if int(record['bsbz']) == 1:
            text_color = wx.GREEN
        elif int(record['bsbz'] == 2):
            text_color = wx.RED
        elif int(record['bsbz'] == 4):
            text_color = wx.BLACK
        return text_color
    
    def getVisibleRowRange(self):
        row_range = []
        row_index = 0
        while(row_index < self.grid.GetNumberRows()):
            if self.grid.IsVisible(row_index, 0):
                row_range.append(row_index)
            row_index = row_index + 1
        return row_range

    def fillGrid(self, record_list, start = 0, end = -1):
        row_range = self.getVisibleRowRange()
        cols_cnt = self.grid.GetNumberCols()
        print(row_range)
        if len(row_range):
            tail_unvisiable_record = self.grid.GetNumberRows() - row_range[-1] - 1
            if 3*(len(record_list) - tail_unvisiable_record) > cols_cnt * len(row_range):
                end = len(record_list) - tail_unvisiable_record
                start = end - int((cols_cnt * len(row_range)) // 3)
            else:
                start = 0
                end = min(len(record_list), int((cols_cnt * len(row_range)) // 3))
        col_index = 0
        record_index = start
        self.showStart = start
        row_idx = 0
        while col_index < cols_cnt:
            row_idx = 0
            while(True):
                row = row_range[row_idx]
                record = record_list[record_index]
                if record_index == 0 or (record_list[record_index]['time'].date() > record_list[record_index - 1]['time'].date()):
                    self.grid.SetCellTextColour(row, col_index, wx.RED)
                    self.grid.SetCellValue(row, col_index, record['time'].strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    self.grid.SetCellTextColour(row, col_index, wx.LIGHT_GREY)
                    self.grid.SetCellValue(row, col_index, record['time'].strftime('%H:%M:%S'))

                text_color = self.getTextColor(record)
                self.grid.SetCellTextColour(row, col_index + 1, text_color)
                self.grid.SetCellValue(row, col_index + 1, '{:.2f}'.format(record['price']))

                self.grid.SetCellTextColour(row, col_index + 2, text_color)
                self.grid.SetCellValue(row, col_index + 2, str(record['shoushu']))

                record_index = record_index + 1
                row_idx = row_idx + 1
                if(row_idx >= len(row_range)):
                    break
                if(record_index >= end):
                    break
            if row_idx >= len(row_range):
                col_index = col_index + 3
            if(record_index >= end):
                break
 
        if row_idx < len(row_range) or col_index < cols_cnt:
            while col_index < cols_cnt:
                while(True):
                    if(row_idx >= len(row_range)):
                        row_idx = 0
                        break
                    row = row_range[row_idx]
                    self.grid.SetCellValue(row, col_index, '   ')
                    self.grid.SetCellValue(row, col_index + 1, '   ')
                    self.grid.SetCellValue(row, col_index + 2, '   ')
                    row_idx = row_idx + 1
                col_index = col_index + 3


        # if end < 0:
        #     end = len(record_list)
        # if start >= end:
        #     start = 0
        # rows_cnt = self.grid.GetNumberRows()
        # cols_cnt = self.grid.GetNumberCols()
        # if 3*(end-start) > rows_cnt * cols_cnt:
        #     start = int(end - rows_cnt * cols_cnt / 3)
        # col_index = 0
        # record_index = start
        # self.showStart = start
        # while col_index < cols_cnt:
        #     for row in range(0, rows_cnt):
        #         record = record_list[record_index]
        #         self.grid.SetCellTextColour(row, col_index, wx.LIGHT_GREY)
        #         self.grid.SetCellValue(row, col_index, record['time'].strftime('%Y-%m-%d %H:%M:%S'))

        #         text_color = self.getTextColor(record)
        #         self.grid.SetCellTextColour(row, col_index + 1, text_color)
        #         self.grid.SetCellValue(row, col_index + 1, str(record['price']))

        #         self.grid.SetCellTextColour(row, col_index + 2, text_color)
        #         self.grid.SetCellValue(row, col_index + 2, str(record['shoushu']))

        #         record_index = record_index + 1
        #         if(record_index >= end):
        #             break
        #     if(record_index >= end):
        #         break
        #     col_index = col_index + 3
        # self.showEnd = record_index

    def onStockListSelected(self, event):
        self.loadData()
        self.expandGrid()
        self.fillGrid(self.stockRecordList)

    def onAddStock(self, event):
        self.selWindow = SelStockWindow(self, wx.ID_ANY, '选择股票')
        self.selWindow.Bind(wx.EVT_CLOSE, self.onSelClose)
        return
    
    def onDeleteStock(self, event):
        global dbSession
        index=self.stockList.GetFirstSelected()
        if index>=0:
            id=self.stockList.GetItemData(index)
            try:
                stock_table=Table(StockTable.__tablename__, Base.metadata, autoload=True)
                deleteQuery=stock_table.delete().where(stock_table.c.id==id)
                dbSession.execute(deleteQuery)
                dbSession.commit()
                self.stockList.DeleteItem(index)
            except Exception as e:
                print(f"Error opening database: {e}")

    def addSelStock(self, stock_data):
        global dbSession
        global dbEngine
        stocks=dbSession.query(StockTable).filter(StockTable.code==stock_data['code']).all()
        if len(stocks) <= 0:
            get_model('stock_'+stock_data['code'])
            Base.metadata.create_all(dbEngine)
            dbSession.add(StockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=datetime.datetime.now()))
            dbSession.commit()
            row=dbSession.query(StockTable).filter(StockTable.code==stock_data['code']).one()
            index = self.stockList.InsertItem(0, stock_data['code'])
            self.stockList.SetItem(index, 1, stock_data['name'])
            self.stockList.SetItemData(index, row.id)


    def onSelClose(self, event):
        if(self.selWindow.selStock):
            self.addSelStock(self.selWindow.selStock)
        event.Skip()

    def createGrid(self):
        # 定义网格的列数和列标题
        self.grid.CreateGrid(0, 18)
        self.grid.SetDefaultRowSize(20)
        # attr = wx.grid.GridCellAttr()
        # attr.Set
        # attr.SetBottomBorder(wx.grid.GRID_BORDER_SOLID)
        # attr.SetTopBorder(wx.grid.GRID_BORDER_SOLID)
        # attr.SetLeftBorder(wx.grid.GRID_BORDER_SOLID)
        # attr.SetRightBorder(wx.grid.GRID_BORDER_SOLID)
        # self.grid.SetDefaultCellAttr(attr)
        self.grid.SetRowLabelSize(0)  # 设置行标签的大小
        self.grid.SetColLabelSize(20)  # 设置列标签的大小
        for i in range(0, 6):
            self.grid.SetColLabelValue(i*3, "时间")
            self.grid.SetColLabelValue(i*3+1, "成交价")
            self.grid.SetColLabelValue(i*3+2, '手数')
        self.grid.AppendRows(1)

        for row in range(self.grid.GetNumberRows()):
            for col in range(self.grid.GetNumberCols()):
                self.grid.SetCellValue(row, col, f"        ")

    def addRecord(self, stock, record):
        global dbEngine
        global dbSession

        StockModel = get_model('stock_' + stock['code'])
        date_format = "%Y-%m-%d %H:%M:%S"
        time = datetime.datetime.strptime(record['time'], date_format)
        rows = dbSession.query(StockModel).filter(StockModel.time == time).all()
        if len(rows) <= 0:
            print(record)
            dbSession.add(StockModel(time=time, price=float(record['price']), shoushu=int(record['shoushu']), bsbz=int(record['bsbz'])))
            dbSession.commit()

    def readFromWeb(self, url, stock):
        print(url)
        response = requests.get(url, headers=global_header)
        if response.status_code == 200:
            response_data = response.json()
            if response_data["msg"] == 'success':
                for record in response_data['data']:
                    self.addRecord(stock, record)

    def updateStockRealTimeHistory(self, stock):
        global dbSession
        StockModel = get_model('stock_'+stock['code'])
        Base.metadata.create_all(dbEngine)        
        latest_record = dbSession.query(StockModel).order_by(StockModel.time.desc()).limit(1).first()
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

 
    def onFileChanged(self, event):
        global dbSession
        global dbEngine
        dbPath=None
        
        fileDialog=wx.FileDialog(self,'打开', wildcard='*.*', style=wx.FD_OPEN)
        if fileDialog.ShowModal() == wx.ID_OK:
            dbPath=fileDialog.GetPath()
        fileDialog.Destroy()

        if dbPath:
            try:
                dbURI='sqlite:///'+dbPath+'?charset=utf8'
                if not dbSession:
                    dbEngine=create_engine(dbURI, echo=True)
                    Session = sessionmaker(bind=dbEngine)
                    dbSession=Session()
                    Base.metadata.create_all(dbEngine)
                    dbSession.commit()
                stocks=dbSession.query(StockTable).all()
                idx=0
                for stock in stocks:
                    self.updateStockRealTimeHistory(stock.to_dict())
                    index=self.stockList.InsertItem(idx,stock.code)
                    self.stockList.SetItem(index, 1, stock.name)
                    self.stockList.SetItemData(index,stock.id)
                    print(stock.id, stock.code, stock.name, stock.createAt, stock.updateAt)
            except Exception as e:
                print(f"Error opening database: {e}")

    def onExit(self, event):
        self.Close()

app = wx.App(False)
frame = MainWindow()
app.MainLoop()

