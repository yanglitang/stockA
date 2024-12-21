
import wx
import wx.grid
import wx.lib
import wx.lib.newevent
import xlrd
import sqlite3
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
from data import AStockTable, StockTable, Base, g_dbsession, g_dbengine, get_model
import datetime
from datetime import timedelta, time, date
import requests
import json
from StocksDB import StocksDB

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
        self.stockListCtrl=wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.stockListCtrl.InsertColumn(0, '股票代码')
        self.stockListCtrl.InsertColumn(1, '股票名称')
        self.stockListCtrl.SetColumnWidth(0, 150)
        self.stockListCtrl.SetColumnWidth(1, 150)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onStockListDoubleClicked, self.stockListCtrl)

        global g_dbsession
        # atable=Table(AStockTable.__tablename__, Base.metadata)
        # sel_stmt=atable.select()
        query = g_dbsession.query(AStockTable)
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
                url=g_sina_stock_list_url.format(i, num)
                print(url)
                response = requests.get(url, headers=g_header)
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
            query = g_dbsession.query(AStockTable)
            db_stocks=query.all()
            stockCntCtrl.SetLabelText('股票总数：%d'%(len(db_stocks)))

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(stockCntCtrl, flag=wx.RIGHT | wx.ALIGN_BOTTOM, border=100)
        buttonSizer.Add(self.stockCodeCtrl, flag=wx.ALIGN_BOTTOM, border=10)
        buttonSizer.Add(search_button, flag=wx.ALIGN_BOTTOM, border=10)
        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(buttonSizer)
        panelSizer.Add(self.stockListCtrl, 1, wx.EXPAND)
        panel.SetSizer(panelSizer)
        self.Centre()
        self.Show()

    def OnClose(self, event):
        self.Destroy()

    def showStock(self, stock_data):
        index=self.stockListCtrl.InsertItem(0, stock_data['code'])
        self.stockListCtrl.SetItem(index, 1, stock_data['name'])

    def addStock(self, stock_data):
        global g_dbsession
        # atable=Table(AStockTable.__tablename__, Base.metadata)
        # sel_stmt=atable.select().where(atable.c.code == stock_data['code'])
        # db_stocks=g_dbsession.execute(sel_stmt)
        db_stocks = g_dbsession.query(AStockTable).filter(AStockTable.code == stock_data['code']).all()
        if len(db_stocks) <= 0:
            g_dbsession.add(AStockTable(code=stock_data['code'], name=stock_data['name'], createAt=datetime.datetime.now(), updateAt=datetime.datetime.now()))
            g_dbsession.commit()
        self.showStock(stock_data)

    def onStockListDoubleClicked(self, event):
        index = event.GetIndex()
        self.selStock['code']=self.stockListCtrl.GetItemText(index, 0)
        self.selStock['name']=self.stockListCtrl.GetItemText(index, 1)
        self.Close()

    def onSearchButton(self, event):
        global g_dbsession
        search_text = self.stockCodeCtrl.GetValue().strip()
        if len(search_text) > 0:
            db_stocks = g_dbsession.query(AStockTable).filter(or_(AStockTable.code.like('%'+search_text+'%'), AStockTable.name.like('%'+search_text+'%'))).all()
            if len(db_stocks) > 0:
                self.stockListCtrl.DeleteAllItems()
                for row in db_stocks:
                    index = self.stockListCtrl.InsertItem(0, row.code)
                    self.stockListCtrl.SetItem(index, 1, row.name)
