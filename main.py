import wx
import wx.grid
import wx.lib
import wx.lib.newevent
import xlrd
import sqlite3
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
from data import AStockTable, StockTable, Base, get_model
import datetime
from datetime import timedelta, time, date
import requests
import json
from StocksDB import StocksDB
from SelStockWindow import SelStockWindow
from GlobalInstance import get_mainwnd, set_mainwnd
from apscheduler.schedulers.background import BackgroundScheduler
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

GREEN_COLOR = (0x00,0xB0,0x50)
FIGURE_CANVAS_HEIGHT_INCHE = 2

EVT_DB_UPDATED_ID = wx.NewId()

def EVT_DB_UPDATED(wnd, func):
    wnd.Connect(-1, -1, EVT_DB_UPDATED_ID, func)

class DBUpdatedEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_DB_UPDATED_ID)
        self.data = data

def update_db_from_internet():
    stock_list = get_mainwnd().stocksDB.loadFocusStocks()
    for stock in stock_list:
        get_mainwnd().stocksDB.updateStockRealTimeHistory(stock)
        wx.PostEvent(get_mainwnd(), DBUpdatedEvent(0))
    get_mainwnd().stocksDB.updateAStockRT()

class MainWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Excel Import")
        self.panel = wx.Panel(self)

        self.selStock = {}
        self.stockRecordList = []
        self.showStart = -1
        self.showEnd = -1
        self.highLightShoushu = -1
        self.stocksDB = StocksDB()
        self.listctlStocks = []
         
        screen_dc = wx.ScreenDC()
        self.pixelAccuracy = (screen_dc.GetPPI()[0], screen_dc.GetPPI()[1])
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
   
        self.stockListCtrl=wx.ListCtrl(self.panel, style=wx.LC_REPORT)
        self.stockListCtrl.InsertColumn(0, '股票代码')
        self.stockListCtrl.InsertColumn(1, '股票名称')
        self.stockListCtrl.InsertColumn(2, '更新时间')
        self.stockListCtrl.SetColumnWidth(0, 150)
        self.stockListCtrl.SetColumnWidth(1, 150)
        self.stockListCtrl.SetColumnWidth(2, 150)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onStockListSelected, self.stockListCtrl)
  
        addStockButton=wx.Button(self.panel, -1, '添加')
        self.Bind(wx.EVT_BUTTON, self.onAddStock, addStockButton)
        deleteStockButton=wx.Button(self.panel, -1, '删除')
        self.Bind(wx.EVT_BUTTON, self.onDeleteStock, deleteStockButton)

        self.filterShoushuCtrl =wx.TextCtrl(self.panel)
        self.filterShoushuCtrl.SetSizeWH(20, -1)
        filter_button = wx.Button(self.panel, -1, '过滤')
        self.Bind(wx.EVT_BUTTON, self.onFilterShoushuClicked, filter_button)

        self.filterPanQianCtrl = wx.CheckBox(self.panel, label='过滤盘前竞价')
        self.filterPanQianCtrl.Bind(wx.EVT_CHECKBOX, self.onFilterPanQianCtrl)

        self.highLightShoushuCtrl =wx.TextCtrl(self.panel)
        self.highLightShoushuCtrl.SetSizeWH(20, -1)
        highlight_button = wx.Button(self.panel, -1, '高亮')
        self.Bind(wx.EVT_BUTTON, self.onHighLightShoushuClicked, highlight_button)

        self.grid = wx.grid.Grid(self.panel)
        self.createGrid()
        self.grid.Bind(wx.EVT_SCROLLWIN, self.onScrollWin)
        self.grid.Bind(wx.EVT_KEY_DOWN, self.onKey)

        self.Bind(wx.EVT_MAXIMIZE, self.onMaxiMize)

        EVT_DB_UPDATED(self, self.onDBUpdated)

        buttonSizer=wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(addStockButton)
        buttonSizer.Add(deleteStockButton)   
        listSizer=wx.BoxSizer(wx.VERTICAL)
 
        listSizer.Add(self.stockListCtrl, 1, wx.EXPAND, 5)
        listSizer.Add(buttonSizer, 0, wx.EXPAND, 5)   

        grid_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        grid_button_sizer.Add(self.filterShoushuCtrl)
        grid_button_sizer.Add(filter_button)
        grid_button_sizer.Add(self.filterPanQianCtrl)
        grid_button_sizer.Add(self.highLightShoushuCtrl)
        grid_button_sizer.Add(highlight_button)

        self.gridSizer = wx.BoxSizer(wx.VERTICAL)
        self.gridSizer.Add(grid_button_sizer, 0, wx.EXPAND, 5)
        self.gridSizer.Add(self.grid, 1, wx.EXPAND, 5)
        # self.gridSizer.Add(self.canvas, 0, wx.EXPAND, 5)

        panelSizer=wx.BoxSizer(wx.HORIZONTAL)
        panelSizer.Add(listSizer, 0, wx.EXPAND)
        panelSizer.Add(self.gridSizer, 1, wx.EXPAND)
        
        self.panel.SetSizer(panelSizer)

        self.Show()

    def getStockDB(self):
        return self.stocksDB

    def loadSelStockRTData(self):
        index = self.stockListCtrl.GetFirstSelected()
        if index >= 0:
            self.selStock['code'] = self.stockListCtrl.GetItemText(index, 0)
            self.selStock['name'] = self.stockListCtrl.GetItemText(index, 1)
            self.stocksDB.reloadStockRTData(self.selStock)

    def onFilterPanQianCtrl(self, event):
        refill_grid = False
        if self.filterPanQianCtrl.GetValue():
            if(self.stocksDB.getPanQian() == True):
                refill_grid =  True
                self.stocksDB.setPanQian(False)
        else:
            if(self.stocksDB.getPanQian() == False):
                refill_grid = True
                self.stocksDB.setPanQian(True)
        if refill_grid:
            self.loadSelStockRTData()
            self.refillGrid()

    def onFilterShoushuClicked(self, event):
        filter_text = self.filterShoushuCtrl.GetValue().strip()
        if len(filter_text) > 0:
            self.stocksDB.setShoushu(int(filter_text))
            self.loadSelStockRTData()
            self.refillGrid()

    def onHighLightShoushuClicked(self, event):
        highlight_text = self.highLightShoushuCtrl.GetValue().strip()
        if len(highlight_text) > 0:
            self.highLightShoushu = int(highlight_text)
        else:
            self.highLightShoushu = 0
        self.refillGrid()

    def onScrollWin(self, event):
        event_type = event.GetEventType()
        self.scrollGrid(event_type)
        if event:
            event.Skip()

    def scrollGrid(self, event_type):
        row_cnt = self.grid.GetNumberRows()
        if row_cnt <= 0:
            self.loadSelStockRTData()
        if self.stocksDB.getStockRTDataCnt() > 0:
            if self.grid.IsVisible(row_cnt - 1, 0) and (event_type == wx.EVT_SCROLL_LINEDOWN or event_type == wx.EVT_SCROLL_PAGEDOWN):
                if self.showEnd >= 0 and self.showEnd < len(self.stocksDB.getStockRTDataCnt()):
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
            self.refillGrid()

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

    def onMaxiMize(self, event):
        self.refillSelStockData()
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
            text_color = GREEN_COLOR
        elif int(record['bsbz'] == 2):
            text_color = wx.RED
        elif int(record['bsbz'] == 4):
            text_color = wx.BLACK
        return text_color
    
    def getVisibleRowRange(self):
        row_range = []
        row_index = 0
        col_index = -1
        while(row_index < self.grid.GetNumberRows()):
            tmp_col_index = 0

            #查找第一个可见列，col_index设置为第一个可见列的索引号，col_index已经被设置过，则不需要再查找
            while(col_index == -1 and tmp_col_index < self.grid.GetNumberCols()):
                if self.grid.IsVisible(row_index, tmp_col_index):
                    #找到第一个可见单元格，那么这个单元格的列号就是第一个可见列
                    col_index = tmp_col_index
                    break
                tmp_col_index = tmp_col_index + 1
            if col_index != -1 and self.grid.IsVisible(row_index, col_index):
                #可见行添加到可见行列表中
                row_range.append(row_index)
            row_index = row_index + 1
        return row_range

    def refillGrid(self):
        start = 0
        end = -1
        record_list = self.stocksDB.getStockRTData()
        row_range = self.getVisibleRowRange()
        cols_cnt = self.grid.GetNumberCols()
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
        print(self.highLightShoushu, col_index, cols_cnt, record_index, end)
        while col_index < cols_cnt:
            row_idx = 0
            if(record_index >= end):
                break            
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

                if(self.highLightShoushu > 0):
                    if(record['shoushu'] >= self.highLightShoushu):
                        for i in range(0,3):
                            if(text_color == wx.RED):
                                self.grid.SetCellBackgroundColour(row, col_index + i, (0xEF, 0X94, 0X9F))
                            if(text_color == GREEN_COLOR):
                                self.grid.SetCellBackgroundColour(row, col_index + i, (0xAD, 0XD8, 0X8D))
                    else:
                        for i in range(0,3):
                            self.grid.SetCellBackgroundColour(row, col_index + i, wx.WHITE)
                else:
                    for i in range(0,3):
                        self.grid.SetCellBackgroundColour(row, col_index + i, wx.WHITE)

                record_index = record_index + 1
                row_idx = row_idx + 1
                if(row_idx >= len(row_range)):
                    break
                if(record_index >= end):
                    break
            if row_idx >= len(row_range):
                col_index = col_index + 3
 
        if row_idx < len(row_range) or col_index < cols_cnt:
            while col_index < cols_cnt:
                while(True):
                    if(row_idx >= len(row_range)):
                        row_idx = 0
                        break
                    row = row_range[row_idx]
                    for i in range(col_index, col_index + 3):
                        self.grid.SetCellValue(row, i, '   ')
                        self.grid.SetCellBackgroundColour(row, i, wx.WHITE)
                    row_idx = row_idx + 1
                col_index = col_index + 3

        self.grid.Refresh()

    def redrawLineChart(self, recrod_list):
        x = [record['time'] for record in recrod_list]
        y = [record['price'] for record in recrod_list]
        self.axes.plot(x, y)
        self.axes.relim()
        self.axes.autoscale_view(True, True, True)
        self.canvas.draw()

    def refillSelStockData(self):
        self.loadSelStockRTData()
        self.expandGrid()
        self.refillGrid()

    def onStockListSelected(self, event):
        self.refillSelStockData()

    def onAddStock(self, event):
        self.selWindow = SelStockWindow(self, wx.ID_ANY, '选择股票')
        self.selWindow.Bind(wx.EVT_CLOSE, self.onSelClose)
        return
    
    def onDeleteStock(self, event):
        index=self.stockListCtrl.GetFirstSelected()
        if index>=0:
            id=self.stockListCtrl.GetItemData(index)
            try:
                self.stocksDB.delFocusStocks(id)
                self.stockListCtrl.DeleteItem(index)
            except Exception as e:
                print(f"Error opening database: {e}")

    def addSelStock(self, stock_data):
        addstock = self.stocksDB.addFocusStocks(stock_data)
        if(addstock[1]):
            stock_data = self.stocksDB.getStock(stock_data['code'])
            insertpos = self.stockListCtrl.GetItemCount()
            index = self.stockListCtrl.InsertItem(insertpos, stock_data['code'])
            self.stockListCtrl.SetItem(index, 1, stock_data['name'])
            self.stockListCtrl.SetItem(index, 2, stock_data['updateAt'].date().strftime('%Y-%m-%d'))
            self.stockListCtrl.SetItemData(index, stock_data['id'])

    def onSelClose(self, event):
        if(self.selWindow.selStock):
            self.addSelStock(self.selWindow.selStock)
        event.Skip()

    def createGrid(self):
        # 定义网格的列数和列标题
        self.grid.CreateGrid(0, 18)
        self.grid.SetDefaultRowSize(20)
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

    def onDBUpdated(self, event):
        sel_stock_updated = False
        sel_stock_last_update_time = ''
        sel_stock_idx = self.stockListCtrl.GetFirstSelected()
        for idx in range(0, self.stockListCtrl.GetItemCount()):
            code = self.stockListCtrl.GetItemText(idx, 0)
            if(idx == sel_stock_idx):
                sel_stock_last_update_time = self.stockListCtrl.GetItemText(idx, 2)
            stock = self.stocksDB.getStock(code)
            if(stock):
                self.stockListCtrl.SetItem(idx, 2, stock['updateAt'].date().strftime('%Y-%m-%d'))
                tmp_text = self.stockListCtrl.GetItemText(idx, 2)
                if(tmp_text != sel_stock_last_update_time):
                    sel_stock_updated =  True
        if(sel_stock_updated):
            self.refillSelStockData()

    def onFileChanged(self, event):
        dbPath=None
        
        fileDialog=wx.FileDialog(self,'打开', wildcard='*.*', style=wx.FD_OPEN)
        if fileDialog.ShowModal() == wx.ID_OK:
            dbPath=fileDialog.GetPath()
        fileDialog.Destroy()

        if dbPath:
            try:
                self.stocksDB.create(dbPath)
                stocks = self.stocksDB.loadFocusStocks()
                self.stocksDB.createAllRTTable()
                self.listctlStocks = sorted(stocks, key=lambda x:x["code"])
                for stock in self.listctlStocks:
                    insertpos = self.stockListCtrl.GetItemCount()
                    index=self.stockListCtrl.InsertItem(insertpos,stock['code'])
                    self.stockListCtrl.SetItem(index, 1, stock['name'])
                    self.stockListCtrl.SetItem(index, 2, stock['updateAt'].date().strftime('%Y-%m-%d'))
                    self.stockListCtrl.SetItemData(index,stock['id'])

                #定期从互联网上更新数据到数据库中
                update_db_task = BackgroundScheduler()
                update_db_task.add_job(update_db_from_internet, 'interval', seconds=5, coalesce=True, max_instances=1)
                update_db_task.start()
            except Exception as e:
                print(f"Error opening database: {e}")

    def onExit(self, event):
        self.Close()

app = wx.App(False)
wnd = MainWindow()
set_mainwnd(wnd)
app.MainLoop()
