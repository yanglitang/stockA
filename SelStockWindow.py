
import wx
import wx.grid
import wx.lib
import wx.lib.newevent
import xlrd
import sqlite3
from sqlalchemy import create_engine, Table, or_
from sqlalchemy.orm import sessionmaker
from data import AStockTable, StockTable, Base, get_model
from data import g_sina_stock_list_url
import datetime
from datetime import timedelta, time, date
import requests
import json
from StocksDB import StocksDB
from GlobalInstance import get_mainwnd

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

        stockdb = get_mainwnd().getStockDB()
        stock_list = stockdb.getAStocks()
        for stock in stock_list:
            self.showStock(stock)
        stockCntCtrl.SetLabelText('股票总数：%d'%(len(stock_list)))

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
        cnt = self.stockListCtrl.GetItemCount()
        index=self.stockListCtrl.InsertItem(cnt, stock_data['code'])
        self.stockListCtrl.SetItem(index, 1, stock_data['name'])

    def onStockListDoubleClicked(self, event):
        index = event.GetIndex()
        self.selStock['code']=self.stockListCtrl.GetItemText(index, 0)
        self.selStock['name']=self.stockListCtrl.GetItemText(index, 1)
        self.Close()

    def onSearchButton(self, event):
        search_text = self.stockCodeCtrl.GetValue().strip()

        if len(search_text) > 0:
            stockdb = get_mainwnd().getStockDB()
            stock_list = stockdb.getAStockAlike(search_text)
            if len(stock_list) > 0:
                self.stockListCtrl.DeleteAllItems()
                for stock in stock_list:
                    self.showStock(stock)

