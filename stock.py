import requests
import json
import threading
import time
import platform
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import pystray
from PIL import Image, ImageTk
import sys
import keyboard
from datetime import datetime, time as dt_time

# 配置日志
log_file = os.path.join(os.path.dirname(__file__), 'stock_quote.log')
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

def log_error(symbol, data, error_message):
    """记录错误到日志文件"""
    logging.error(f"Error fetching data for {symbol}. Data: {data}. Error: {error_message}")


class StockQuoteGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("带薪看盘")
        self.root.geometry("800x600")
        
        # 创建一个共享的 Session
        self.session = requests.Session()
        
        # 设置窗口图标（如果图标文件存在）
        self.set_window_icon()
        
        # 创建菜单栏
        self.create_menu()
        
        # 从文件加载自选股
        self.default_stocks = self.load_favorites()
        self.default_indexes = self.load_indexes()
        
        # 当前股票列表
        self.current_stocks = self.default_stocks.copy()
        self.current_mode = 'favorites'  # 'favorites' or 'indexes'
        
        # 盘前盘后数据开关
        self.show_extended_data = tk.BooleanVar(value=False)
        self.show_trading_only = tk.BooleanVar(value=True)
        self.last_stock_data = []
        
        # 刷新间隔（秒）
        self.refresh_interval = 30
        
        # 控制刷新的标志
        self.refresh_active = False
        self.last_refresh_time = time.time()
        
        # 系统托盘相关
        self.icon = None
        self.is_minimized_to_tray = False
        self.setup_tray_icon()
        
        # 创建界面
        self.create_widgets()
        
        # 获取初始数据
        self.trigger_data_load()
        
        # 启动自动刷新
        self.refresh_active = True
        self.root.after(1000, self.refresh_worker)
    
    def create_menu(self):
        # 创建菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 创建帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def show_about(self):
        # 创建关于对话框
        about_text = """带薪看盘

版本: 1.2
作者: GuoQiang
版权: Copyright (c) 2025 BigDragonSoft

这是一款简洁好用的看盘小工具，可以帮你轻松关注股票、外汇和加密货币的行情。

我们加了一些实用的小功能，比如可以自由显示或隐藏美股的盘前盘后价格，也可以一键筛选出还在交易的品种。希望这些功能能让你在看盘时更得心应手！

项目地址: https://github.com/bigdragonsoft/stock-quote
"""
        messagebox.showinfo("关于", about_text)
    
    def load_favorites(self):
        """
        从文件加载自选股列表
        """
        favorites_file = os.path.join(os.path.dirname(__file__), 'favorites.json')
        try:
            if os.path.exists(favorites_file):
                with open(favorites_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('stocks', [])
            else:
                # 如果文件不存在，创建默认文件
                default_favorites = ["SH513100", "SH513500", "SH513180", "IBIT"]
                self.save_favorites(default_favorites)
                return default_favorites
        except Exception as e:
            log_error("FAVORITES", "", f"Error loading favorites file: {e}")
            return ["SH513100", "SH513500", "SH513180", "IBIT"]
    
    def save_favorites(self, favorites):
        """
        将自选股列表保存到文件
        """
        favorites_file = os.path.join(os.path.dirname(__file__), 'favorites.json')
        try:
            with open(favorites_file, 'w', encoding='utf-8') as f:
                json.dump({'stocks': favorites}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_error("FAVORITES", "", f"Error saving favorites file: {e}")

    def load_indexes(self):
        """
        从文件加载指数列表
        """
        indexes_file = os.path.join(os.path.dirname(__file__), 'indexes.json')
        try:
            if os.path.exists(indexes_file):
                with open(indexes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('indexes', [])
            else:
                # 如果文件不存在，创建默认文件
                default_indexes = [
                    "SH000001", "SZ399001", "SZ399006", "SH000688",
                    "SH000016", "BJ899050", "HKHSI", "HKHSTECH",
                    ".DJI", ".IXIC", ".INX"
                ]
                self.save_indexes(default_indexes)
                return default_indexes
        except Exception as e:
            log_error("INDEXES", "", f"Error loading indexes file: {e}")
            return []

    def save_indexes(self, indexes):
        """
        将指数列表保存到文件
        """
        indexes_file = os.path.join(os.path.dirname(__file__), 'indexes.json')
        try:
            with open(indexes_file, 'w', encoding='utf-8') as f:
                json.dump({'indexes': indexes}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_error("INDEXES", "", f"Error saving indexes file: {e}")
    
    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建控制按钮框架
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 状态变量初始化
        self.status_var = tk.StringVar(value="就绪")
        self.remaining_time_var = tk.StringVar(value="")
        
        # --- 左侧控件 ---
        # 自选股按钮
        self.favorites_button = ttk.Button(control_frame, text="显示自选股", command=self.show_favorites)
        self.favorites_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 指数按钮
        self.indexes_button = ttk.Button(control_frame, text="显示指数", command=self.show_indexes)
        self.indexes_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 编辑按钮
        self.edit_button = ttk.Button(control_frame, text="管理股票", command=self.toggle_edit_frame)
        self.edit_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 盘前盘后数据开关
        self.ext_data_button = ttk.Checkbutton(control_frame, text="显示盘前/盘后", 
                                              variable=self.show_extended_data, 
                                              command=self.update_gui_with_data)
        self.ext_data_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 仅显示交易中开关
        self.trading_only_button = ttk.Checkbutton(control_frame, text="仅显示交易中",
                                                   variable=self.show_trading_only,
                                                   command=self.update_gui_with_data)
        self.trading_only_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # --- 右侧控件 (反向打包) ---
        # 隐藏到系统托盘按钮
        tray_button = ttk.Button(control_frame, text="隐藏到托盘", command=self.minimize_to_tray)
        tray_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        # 开始/停止刷新按钮
        self.toggle_button = ttk.Button(control_frame, text="停止刷新", command=self.toggle_refresh)
        self.toggle_button.pack(side=tk.RIGHT)
        
        # 手动刷新按钮
        refresh_button = ttk.Button(control_frame, text="刷新", command=self.trigger_data_load)
        refresh_button.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 刷新间隔设置
        self.interval_var = tk.StringVar(value=str(self.refresh_interval))
        interval_spinbox = ttk.Spinbox(control_frame, from_=5, to=300, width=5, 
                                      textvariable=self.interval_var, 
                                      command=self.update_interval)
        interval_spinbox.pack(side=tk.RIGHT, padx=(0, 5))
        # 绑定回车键事件
        interval_spinbox.bind('<Return>', lambda event: self.update_interval())
        ttk.Label(control_frame, text="刷新间隔(秒):").pack(side=tk.RIGHT)
        
        # 设置全局快捷键
        keyboard.add_hotkey('ctrl+alt+z', self.minimize_to_tray)
        
        # 创建编辑框架（默认隐藏）
        self.edit_frame = ttk.Frame(main_frame)
        self.edit_frame_visible = False
        
        # 默认隐藏编辑框架
        self.edit_frame.pack_forget()
        
        # 股票代码输入框
        ttk.Label(self.edit_frame, text="股票代码:").pack(side=tk.LEFT)
        self.stock_entry = ttk.Entry(self.edit_frame, width=30)
        self.stock_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        # 添加按钮
        add_button = ttk.Button(self.edit_frame, text="添加", command=self.add_stock)
        add_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 删除按钮
        remove_button = ttk.Button(self.edit_frame, text="删除", command=self.remove_stock)
        remove_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 创建股票列表框架
        self.list_frame = ttk.Frame(main_frame)
        # 默认隐藏列表框架
        self.list_frame.pack_forget()
        
        # 创建列表框和滚动条
        scrollbar = ttk.Scrollbar(self.list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.stock_listbox = tk.Listbox(self.list_frame, yscrollcommand=scrollbar.set)
        self.stock_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.stock_listbox.yview)
        
        # 绑定拖放事件
        self.stock_listbox.bind('<Button-1>', self.on_drag_start)
        self.stock_listbox.bind('<B1-Motion>', self.on_drag_motion)
        self.stock_listbox.bind('<ButtonRelease-1>', self.on_drop)
        self.drag_start_index = None
        
        # 添加默认股票到列表框
        for stock in self.current_stocks:
            self.stock_listbox.insert(tk.END, stock)
        
        # 创建结果显示区域 - 使用Frame和Grid布局来显示表格
        self.result_frame = ttk.Frame(main_frame)
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 创建Canvas和滚动条以支持滚动
        self.canvas = tk.Canvas(self.result_frame)
        v_scrollbar = ttk.Scrollbar(self.result_frame, orient="vertical", command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(self.result_frame, orient="horizontal", command=self.canvas.xview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 修改布局管理器的使用
        self.canvas.grid(row=0, column=0, sticky='nsew')  # 使用 grid 布局
        v_scrollbar.grid(row=0, column=1, sticky='ns')    # 使用 grid 布局
        h_scrollbar.grid(row=1, column=0, sticky='ew')    # 使用 grid 布局
        
        self.result_frame.rowconfigure(0, weight=1)
        self.result_frame.columnconfigure(0, weight=1)

        # 创建状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        remaining_time_label = ttk.Label(status_frame, textvariable=self.remaining_time_var, relief=tk.SUNKEN, anchor=tk.W, width=15)
        remaining_time_label.pack(side=tk.RIGHT, padx=(1, 0))
        
        # 初始化状态栏
        self.update_status_bar()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化状态栏显示
        self.update_status_bar()
    
    def toggle_edit_frame(self):
        """
        切换编辑框架的显示和隐藏
        """
        if self.edit_frame_visible:
            self.edit_frame.pack_forget()
            self.list_frame.pack_forget()
            self.edit_button.config(text="管理股票")
            self.edit_frame_visible = False
        else:
            self.edit_frame.pack(fill=tk.X, pady=(0, 10))
            self.list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            self.edit_button.config(text="隐藏编辑")
            self.edit_frame_visible = True

    # 外汇代码映射表
    forex_code_map = {
        "JPYUSD": {"secid": "119.JPYUSD", "name": "日元/美元"},
        "USDCNH": {"secid": "133.USDCNH", "name": "美元/人民币"},
        "EURUSD": {"secid": "119.EURUSD", "name": "欧元/美元"},
        "GBPUSD": {"secid": "119.GBPUSD", "name": "英镑/美元"},
        "AUDUSD": {"secid": "119.AUDUSD", "name": "澳元/美元"},
        "USDJPY": {"secid": "119.USDJPY", "name": "美元/日元"},
        "USDCHF": {"secid": "119.USDCHF", "name": "美元/瑞郎"},
        "USDCAD": {"secid": "119.USDCAD", "name": "美元/加元"},
        "USDHKD": {"secid": "119.USDHKD", "name": "美元/港币"},
        "EURJPY": {"secid": "119.EURJPY", "name": "欧元/日元"},
        "GBPJPY": {"secid": "119.GBPJPY", "name": "英镑/日元"}
    }
    
    def is_forex_symbol(self, symbol):
        """
        判断是否为外汇符号
        外汇符号格式如: USDCNH, USDJPY, EURUSD 等
        """
        # 首先检查是否在映射表中
        if symbol.upper() in self.forex_code_map:
            return True
        # 外汇代码通常是6个字母组成，前3个是基础货币，后3个是报价货币
        return bool(re.match(r'^[A-Z]{6}$', symbol)) and symbol != "SH513100" and symbol != "SH513500" and symbol != "SH513180" and symbol != "IBIT"
    
    def is_crypto_symbol(self, symbol):
        """
        判断是否为加密货币符号
        """
        crypto_symbols = ['BTC', 'ETH', 'XRP', 'USDT', 'BNB', 'SOL', 'USDC', 'DOGE', 'ADA', 'SHIB']
        return symbol.upper() in crypto_symbols

    def get_crypto_info(self, symbol):
        """
        从528btc网站获取加密货币信息
        """
        symbol = symbol.upper()
        
        # 定义加密货币映射
        crypto_mapping = {
            'BTC': {'name': 'Bitcoin', 'id': 3008},
            'ETH': {'name': 'Ethereum', 'id': 3007},
            'XRP': {'name': 'Ripple', 'id': 3006},
            'USDT': {'name': 'Tether', 'id': 32675},
            'BNB': {'name': 'Binance Coin', 'id': 3155},
            'SOL': {'name': 'Solana', 'id': 10114},
            'USDC': {'name': 'USD Coin', 'id': 8249},
            'DOGE': {'name': 'Dogecoin', 'id': 2993},
            'ADA': {'name': 'Cardano', 'id': 3010},
            'SHIB': {'name': 'Shiba Inu', 'id': 10547},
        }
        
        if symbol not in crypto_mapping:
            return None
        
        html_content = ""
        try:
            url = f"https://www.528btc.com/coin/{crypto_mapping[symbol]['id']}/kline-24h"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.528btc.com/"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # 解析HTML内容
            html_content = response.text
            
            # 提取价格信息
            price_match = re.search(r'<i class="price_num word(Rise|Fall)">\$?([0-9,]+\.?[0-9]*)</i>', html_content)
            change_match = re.search(r'<span id="rise_fall_amount"[^>]*class="word(Rise|Fall)">([+-])\$?([0-9,]+\.?[0-9]*)</span>', html_content)
            percent_match = re.search(r'<div id="rise_fall_percent"[^>]*>([+-]?)(?:\s*)([0-9]+\.?[0-9]*)\s*%', html_content)
            
            if not price_match:
                log_error(symbol, html_content, "Could not parse price information")
                return None
            
            # 处理价格中的逗号
            price_str = price_match.group(2)
            price = float(price_str.replace(',', ''))
            
            change = 0.0
            percent = 0.0
            
            if change_match:
                # 获取符号和数值
                sign = change_match.group(2)  # '+' 或 '-'
                change_str = change_match.group(3)  # 数值部分
                change_value = float(change_str.replace(',', ''))
                # 应用符号
                if sign == '-':
                    change = -change_value
                else:
                    change = change_value
            
            if percent_match:
                # 正确处理正负号
                sign = percent_match.group(1)  # '+' 或 '-'
                percent_value = float(percent_match.group(2))
                if sign == '-':
                    percent = -percent_value
                else:
                    percent = percent_value
                
            crypto_info = {
                "Region": "CRYPTO",
                "Status": "-", 
                "Name": crypto_mapping[symbol]['name'],
                "Symbol": symbol,
                "Price": price,
                "Change": change,
                "Percent": f"{percent:.2f}%"
            }
            
            return crypto_info
            
        except requests.exceptions.RequestException as e:
            log_error(symbol, "", f"Request error: {e}")
            return None
        except json.JSONDecodeError:
            log_error(symbol, response_text, "JSON parsing error")
            return None
        except Exception as e:
            log_error(symbol, response_text, f"Unknown error: {e}")
            return None

    def get_eastmoney_forex_info(self, symbol):
        """
        从东方财富网获取外汇信息
        支持映射表中的外汇代码和通用的6位外汇代码
        """
        try:
            symbol = symbol.upper()
            
            # 获取对应的secid
            if symbol in self.forex_code_map:
                # 使用预定义的secid
                secid = self.forex_code_map[symbol]['secid']
                name = self.forex_code_map[symbol]['name']
            else:
                # 对于不在映射表中的外汇代码，尝试构造通用的secid
                # 大多数外汇使用119作为市场代码
                secid = f"119.{symbol}"
                # 构造一个通用的名称
                if len(symbol) == 6:
                    base_currency = symbol[:3]
                    quote_currency = symbol[3:]
                    name = f"{base_currency}/{quote_currency}"
                else:
                    name = symbol
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Referer': f'https://quote.eastmoney.com/forex/{symbol}.html'
            }
            
            # 请求东方财富网外汇API
            api_url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f170,f171,f168"
            
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析JSON数据
            data = response.json()
            
            if data and 'data' in data and data['data'] is not None:
                api_data = data['data']
                
                # 提取名称，如果API返回了名称则使用API的名称
                if 'f58' in api_data and api_data['f58']:
                    name = api_data.get('f58')
                
                # 提取当前价格 (f43)
                current_price = None
                if 'f43' in api_data and api_data['f43']:
                    current_price = api_data['f43'] / 10000
                
                # 计算涨跌额 (f43 - f60)
                change_amount = None
                if 'f43' in api_data and 'f60' in api_data and api_data['f43'] and api_data['f60']:
                    change_amount = (api_data['f43'] - api_data['f60']) / 10000
                
                # 提取涨跌幅 (f170)
                change_percent = None
                if 'f170' in api_data and api_data['f170']:
                    change_percent = api_data['f170'] / 100  # 转换为百分比
                
                forex_info = {
                    "Region": "FX",
                    "Status": "-",
                    "Name": name,
                    "Symbol": symbol,
                    "Price": current_price,
                    "Change": change_amount,
                    "Percent": f"{change_percent:.2f}%" if change_percent is not None else "0.00%"
                }
                
                return forex_info
            else:
                # 如果不在映射表中且东方财富网没有数据，返回错误
                error_message = f"未能获取到有效的数据: {symbol}"
                log_error(symbol, str(data), error_message)
                return None
                
        except requests.exceptions.RequestException as e:
            error_message = f"网络连接失败: {e}"
            log_error(symbol, "", error_message)
            return None
        except json.JSONDecodeError as e:
            error_message = f"解析JSON数据失败: {e}"
            log_error(symbol, "", error_message)
            return None
        except Exception as e:
            error_message = f"发生未知错误: {e}"
            log_error(symbol, "", error_message)
            return None

    def get_forex_info(self, symbol):
        """
        获取外汇信息，使用东方财富网API
        """
        return self.get_eastmoney_forex_info(symbol)
    
    def get_stock_info(self, symbol):
        """
        从腾讯获取股票信息
        """
        # 判断是否为加密货币
        if self.is_crypto_symbol(symbol):
            return self.get_crypto_info(symbol)
        
        # 判断是否为外汇
        if self.is_forex_symbol(symbol):
            return self.get_forex_info(symbol)

        # 格式化 symbol
        symbol_lower = symbol.lower()
        market_symbol = ""
        market_type = ""
        if symbol_lower.startswith(('sh', 'sz')):
            market_symbol = symbol_lower
            market_type = "A-Share"
        elif symbol_lower.startswith('.'): # 指数
            market_symbol = f"s_us{symbol_lower}"
            market_type = "Index"
        elif symbol_lower.startswith('hkhsi'):
            market_symbol = "s_hkHSI"
            market_type = "HK-Index"
        elif symbol_lower.startswith('hkhstech'):
            market_symbol = "s_hkHSTECH"
            market_type = "HK-Index"
        elif symbol_lower.startswith(('hk')):
            market_symbol = f"hk{symbol_lower[2:]}"
            market_type = "HK-Share"
        else: # 默认美股
            market_symbol = f"us{symbol.upper()}"
            market_type = "US-Share"

        url = f"https://qt.gtimg.cn/q={market_symbol}"
        response_text = ""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
                "Referer": "https://gu.qq.com/"
            }
            response = self.session.get(url, headers=headers, verify=False)
            response_text = response.text
            response.raise_for_status()

            # 解析返回的字符串
            data_part = response_text.split('=')[1].strip('"\n;')
            if not data_part or "none" in data_part:
                log_error(symbol, response_text, f"No data found for symbol: {symbol}")
                return None

            if not data_part or "none" in data_part:
                log_error(symbol, response_text, f"No data found for symbol: {symbol}")
                return None

            parts = data_part.split('~')
            
            stock_info = {}
            if market_type in ["Index", "HK-Index"]:
                stock_info = {
                    "Region": "INDEX",
                    "Status": "-",
                    "Name": parts[1],
                    "Symbol": symbol,
                    "Price": float(parts[3]),
                    "Change": float(parts[4]),
                    "Percent": f"{float(parts[5]):.2f}%"
                }
            elif market_type == "US-Share":
                status = "OPEN" if parts[0] == 'us' else "CLOSED"
                stock_info = {
                    "Region": "US",
                    "Status": status,
                    "Name": parts[1],
                    "Symbol": symbol,
                    "Price": float(parts[3]),
                    "Change": float(parts[31]),
                    "Percent": f"{float(parts[32]):.2f}%",
                    "extPrice": float(parts[22]),
                    "extChange": float(parts[23]),
                    "extPercent": f"{float(parts[24]):.2f}%"
                }
            else: # A-Share / HK-Share
                region = "SH" if symbol.startswith("SH") else "SZ" if symbol.startswith("SZ") else "HK"
                status = self.get_market_status(region)
                stock_info = {
                    "Region": region,
                    "Status": status,
                    "Name": parts[1],
                    "Symbol": symbol,
                    "Price": float(parts[3]),
                    "Change": float(parts[31]),
                    "Percent": f"{float(parts[32]):.2f}%"
                }
            
            return stock_info

        except requests.exceptions.RequestException as e:
            log_error(symbol, "", f"Request error: {e}")
            return None
        except (IndexError, ValueError) as e:
            log_error(symbol, response_text, f"Parsing error: {e}")
            return None
        except Exception as e:
            log_error(symbol, response_text, f"Unknown error: {e}")
            return None
    
    def get_market_status(self, market):
        """
        根据当前时间判断市场状态
        """
        now = datetime.now()
        weekday = now.weekday()  # Monday is 0 and Sunday is 6
        
        # Weekend
        if weekday >= 5:
            return "CLOSED"
        
        current_time = now.time()
        
        if market in ["SH", "SZ"]:  # A股市场
            # A股交易时间:
            # 上午: 9:30 - 11:30
            # 下午: 13:00 - 15:00
            morning_open = dt_time(9, 30)
            morning_close = dt_time(11, 30)
            afternoon_open = dt_time(13, 0)
            afternoon_close = dt_time(15, 0)
            
            if (morning_open <= current_time <= morning_close) or \
               (afternoon_open <= current_time <= afternoon_close):
                return "OPEN"
            else:
                return "CLOSED"
                
        elif market == "HK":  # 港股市场
            # 港股交易时间:
            # 上午: 9:30 - 12:00
            # 下午: 13:00 - 16:00
            morning_open = dt_time(9, 30)
            morning_close = dt_time(12, 0)
            afternoon_open = dt_time(13, 0)
            afternoon_close = dt_time(16, 0)
            
            if (morning_open <= current_time <= morning_close) or \
               (afternoon_open <= current_time <= afternoon_close):
                return "OPEN"
            else:
                return "CLOSED"
        
        # Default case
        return "-"
    
    def trigger_data_load(self):
        """
        在后台线程中触发数据加载
        """
        self.status_var.set("正在获取数据...")
        # 使用线程以避免阻塞GUI
        threading.Thread(target=self.load_stock_data, daemon=True).start()

    def load_stock_data(self):
        """
        加载并显示股票数据（在后台线程中运行）
        """
        if not self.current_stocks:
            self.last_stock_data = []
            # 在主线程中更新GUI
            self.root.after(0, self.update_gui_with_data)
            return
        
        all_stock_info = []
        # 使用线程池并发获取数据
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 创建一个从 future 到 symbol 的映射
            future_to_symbol = {executor.submit(self.get_stock_info, symbol): symbol for symbol in self.current_stocks}
            
            for future in as_completed(future_to_symbol):
                try:
                    stock_info = future.result()
                    if stock_info:
                        all_stock_info.append(stock_info)
                except Exception as e:
                    symbol = future_to_symbol[future]
                    log_error(symbol, "", f"Error getting data for {symbol}: {e}")

        # 按原始顺序排序结果
        symbol_order = {symbol: i for i, symbol in enumerate(self.current_stocks)}
        all_stock_info.sort(key=lambda x: symbol_order.get(x['Symbol'], float('inf')))

        # 保存最新数据
        self.last_stock_data = all_stock_info
        # 在主线程中更新GUI
        self.root.after(0, self.update_gui_with_data)

    def update_gui_with_data(self):
        """
        用获取到的数据更新GUI（在主线程中运行）
        """
        all_stock_info = self.last_stock_data
        
        # 如果选中，则只显示交易中的数据
        if self.show_trading_only.get():
            all_stock_info = [stock for stock in all_stock_info if stock.get('Status') != "CLOSED"]
            
        # 清除现有内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        if not self.current_stocks:
            label = ttk.Label(self.scrollable_frame, text="请添加股票代码")
            label.pack()
            self.status_var.set("就绪")
            return

        if all_stock_info:
            # 创建表格框架
            table_frame = ttk.Frame(self.scrollable_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Check if any stock has extended data to decide if we need the extra columns.
            has_ext_data = self.show_extended_data.get() and any("extPrice" in d for d in all_stock_info)

            # 定义列宽权重和最小宽度
            column_config = [
                {"name": "Region", "weight": 1, "minsize": 60},
                {"name": "Status", "weight": 1, "minsize": 60},
                {"name": "Symbol", "weight": 2, "minsize": 100},
                {"name": "Price", "weight": 1, "minsize": 80},
                {"name": "Change", "weight": 1, "minsize": 80},
                {"name": "Percent", "weight": 1, "minsize": 80},
                {"name": "Name", "weight": 3, "minsize": 120}
            ]
            if has_ext_data:
                # Insert extended data after 'Name'
                name_index = next((i for i, col in enumerate(column_config) if col["name"] == "Name"), -1)
                if name_index != -1:
                    ext_columns = [
                        {"name": "extPrice", "weight": 1, "minsize": 80},
                        {"name": "extChange", "weight": 1, "minsize": 80},
                        {"name": "extPercent", "weight": 1, "minsize": 80},
                    ]
                    column_config = column_config[:name_index+1] + ext_columns + column_config[name_index+1:]

            
            # 创建表头
            headers = [col["name"] for col in column_config]
            for col, header in enumerate(headers):
                label = ttk.Label(table_frame, text=header, font=("Arial", 10, "bold"), 
                                 borderwidth=1, relief="solid", padding=(5, 2))
                label.grid(row=0, column=col, sticky="ew")
            
            # 添加数据行
            for row, stock in enumerate(all_stock_info, start=1):
                # 根据状态设置显示的文字
                status_text = stock.get('Status', '')
                if '收盘' in status_text or 'halt' in status_text.lower():
                    status_display = "CLOSED"
                elif '交易' in status_text or 'trading' in status_text.lower():
                    status_display = "OPEN"
                else:
                    status_display = "-"
                
                # 显示每列数据
                data_values = [stock.get(col['name'], '-') for col in column_config]
                
                for col, value in enumerate(data_values):
                    label = ttk.Label(table_frame, text=str(value), 
                                     borderwidth=1, relief="solid", padding=(5, 2))
                    label.grid(row=row, column=col, sticky="ew")
            
            # 配置列权重和最小尺寸
            for i, config in enumerate(column_config):
                table_frame.columnconfigure(i, weight=config["weight"], minsize=config["minsize"])
        else:
            # 显示错误信息
            label = ttk.Label(self.scrollable_frame, text="未能获取任何股票数据")
            label.pack()
        
        # 更新状态栏
        self.status_var.set(f"上次更新: {time.strftime('%H:%M:%S')} - 刷新间隔: {self.refresh_interval}秒")
        self.last_refresh_time = time.time()
    
    def add_stock(self):
        """
        添加股票代码
        """
        stock_code = self.stock_entry.get().strip().upper()
        if not stock_code:
            messagebox.showwarning("输入错误", "请输入股票代码")
            return
        
        if stock_code in self.current_stocks:
            messagebox.showwarning("重复添加", f"股票 {stock_code} 已存在")
            return
        
        self.current_stocks.append(stock_code)
        self.stock_listbox.insert(tk.END, stock_code)
        self.stock_entry.delete(0, tk.END)
        self.trigger_data_load()
        # 根据当前模式保存到对应的文件
        if self.current_mode == 'favorites':
            self.save_favorites(self.current_stocks)
        else:
            self.save_indexes(self.current_stocks)
    
    def remove_stock(self):
        """
        删除选中的股票代码
        """
        selection = self.stock_listbox.curselection()
        if not selection:
            messagebox.showwarning("选择错误", "请在列表中选择要删除的股票")
            return
        
        index = selection[0]
        stock_code = self.stock_listbox.get(index)
        self.current_stocks.remove(stock_code)
        self.stock_listbox.delete(index)
        self.trigger_data_load()
        # 根据当前模式保存到对应的文件
        if self.current_mode == 'favorites':
            self.save_favorites(self.current_stocks)
        else:
            self.save_indexes(self.current_stocks)
    
    def update_interval(self):
        """
        更新刷新间隔
        """
        try:
            new_interval = int(self.interval_var.get())
            if 5 <= new_interval <= 300:
                self.refresh_interval = new_interval
                self.status_var.set(f"刷新间隔已更新为 {self.refresh_interval}秒")
            else:
                messagebox.showwarning("输入错误", "刷新间隔必须在5-300秒之间")
                self.interval_var.set(str(self.refresh_interval))
        except ValueError:
            messagebox.showwarning("输入错误", "请输入有效的数字")
            self.interval_var.set(str(self.refresh_interval))
    
    def toggle_refresh(self):
        """
        开始/停止自动刷新
        """
        self.refresh_active = not self.refresh_active
        if self.refresh_active:
            self.toggle_button.config(text="停止刷新")
            self.update_status_bar(f"自动刷新已启动 - 刷新间隔: {self.refresh_interval}秒")
            # 重启刷新工作线程
            self.root.after(1000, self.refresh_worker)
            # 初始化倒计时显示
            remaining = int(self.refresh_interval - (time.time() - self.last_refresh_time))
            self.remaining_time_var.set(f"下次刷新: {remaining}秒")
        else:
            self.toggle_button.config(text="开始刷新")
            self.update_status_bar("自动刷新已停止")
            self.remaining_time_var.set("")
    
    def show_indexes(self):
        """
        显示指数
        """
        self.current_mode = 'indexes'
        
        # 禁用编辑功能
        self.edit_button.config(state=tk.DISABLED)
        if self.edit_frame_visible:
            self.toggle_edit_frame()
            
        # 从文件加载指数列表
        self.current_stocks = self.load_indexes()
        
        # 更新列表框
        self.stock_listbox.delete(0, tk.END)
        for stock in self.current_stocks:
            self.stock_listbox.insert(tk.END, stock)
        
        # 加载数据
        self.trigger_data_load()
        
        # 更新状态栏
        self.update_status_bar("已加载指数列表")
    
    def show_favorites(self):
        """
        显示自选股
        """
        self.current_mode = 'favorites'
        
        # 启用编辑功能
        self.edit_button.config(state=tk.NORMAL)
        
        # 从文件重新加载自选股，以确保获取最新列表
        self.current_stocks = self.load_favorites()
        
        # 更新列表框
        self.stock_listbox.delete(0, tk.END)
        for stock in self.current_stocks:
            self.stock_listbox.insert(tk.END, stock)
        
        # 加载数据
        self.trigger_data_load()
        
        # 更新状态栏
        self.update_status_bar("已加载自选股列表")
    
    def refresh_worker(self):
        """
        刷新工作函数
        """
        if self.refresh_active:
            current_time = time.time()
            if current_time - self.last_refresh_time >= self.refresh_interval:
                self.trigger_data_load()
                # last_refresh_time will be updated in update_gui_with_data
            else:
                remaining = int(self.refresh_interval - (current_time - self.last_refresh_time))
                self.remaining_time_var.set(f"下次刷新: {remaining}秒")
            
            # 每秒调用一次
            self.root.after(1000, self.refresh_worker)
    
    def update_status_bar(self, message=None):
        """
        更新状态栏显示
        """
        if message:
            self.status_var.set(message)
        else:
            self.status_var.set(f"上次更新: {time.strftime('%H:%M:%S')} - 刷新间隔: {self.refresh_interval}秒")
    
    def setup_tray_icon(self):
        """
        设置系统托盘图标
        """
        try:
            # 尝试加载图标文件
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if not os.path.exists(icon_path):
                icon_path = os.path.join(os.path.dirname(__file__), 'stock_icon.ico')
            
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                # 如果没有图标文件，创建一个简单的图标
                image = Image.new('RGB', (64, 64), color = (73, 109, 137))
            
            # 创建托盘图标菜单
            menu = (
                pystray.MenuItem('显示', self.show_window),
                pystray.MenuItem('退出', self.quit_app)
            )
            
            # 创建托盘图标
            self.icon = pystray.Icon("stock_quote", image, "带薪看盘", menu)
            
            # 在单独的线程中运行托盘图标
            threading.Thread(target=self.icon.run, daemon=True).start()
            
        except Exception as e:
            log_error("TRAY_ICON", "", f"Error setting up tray icon: {e}")
    
    def minimize_to_tray(self):
        """
        最小化到系统托盘
        """
        self.root.withdraw()  # 隐藏窗口
        self.is_minimized_to_tray = True
    
    def show_window(self, icon=None, item=None):
        """
        从系统托盘恢复窗口
        """
        self.root.deiconify()  # 显示窗口
        self.root.lift()  # 将窗口提升到顶层
        self.is_minimized_to_tray = False
    
    def quit_app(self, icon=None, item=None):
        """
        从系统托盘退出应用
        """
        if self.icon:
            self.icon.stop()
        self.refresh_active = False
        self.root.destroy()
    
    def on_closing(self):
        """
        窗口关闭事件处理
        """
        self.refresh_active = False
        if self.icon:
            self.icon.stop()
        self.root.destroy()
    
    def on_drag_start(self, event):
        """
        记录拖动开始时的项目索引
        """
        widget = event.widget
        index = widget.nearest(event.y)
        
        # 检查点击是否在有效项目上
        if 0 <= index < widget.size():
            # 激活该项，以便视觉上确认
            widget.activate(index)
            self.drag_start_index = index
        else:
            self.drag_start_index = None

    def on_drag_motion(self, event):
        """
        在拖动时更新列表框中的项目位置
        """
        if self.drag_start_index is None:
            return
        
        widget = event.widget
        current_index = widget.nearest(event.y)
        
        if current_index != -1 and current_index != self.drag_start_index:
            # 获取拖动的项目
            item = widget.get(self.drag_start_index)
            
            # 从原位置删除
            widget.delete(self.drag_start_index)
            
            # 插入到新位置
            widget.insert(current_index, item)
            
            # 更新拖动开始的索引
            self.drag_start_index = current_index

    def on_drop(self, event):
        """
        拖放结束时，更新数据源并保存
        """
        if self.drag_start_index is None:
            return
        
        # 更新 current_stocks 列表
        self.current_stocks = list(self.stock_listbox.get(0, tk.END))
        
        # 根据当前模式保存到对应的文件
        if self.current_mode == 'favorites':
            self.save_favorites(self.current_stocks)
        else:
            self.save_indexes(self.current_stocks)
        
        # 重新加载主视图以反映顺序
        self.trigger_data_load()
        
        # 重置拖动索引
        self.drag_start_index = None
    
    def set_window_icon(self):
        """
        设置窗口图标
        """
        icon_to_log = "icon"
        try:
            # 根据操作系统选择不同的图标设置方法
            if platform.system() == "Windows":
                # Windows 使用 .ico 文件
                icon_files = ['icon.ico', 'stock_icon.ico']
                for icon_file in icon_files:
                    icon_to_log = icon_file
                    icon_path = os.path.join(os.path.dirname(__file__), icon_file)
                    if os.path.exists(icon_path):
                        self.root.iconbitmap(icon_path)
                        break
            else:
                # macOS 和 Linux 使用 PhotoImage
                # 尝试使用 .png 文件
                icon_to_log = 'icon.png'
                png_icon_path = os.path.join(os.path.dirname(__file__), icon_to_log)
                if os.path.exists(png_icon_path):
                    photo = tk.PhotoImage(file=png_icon_path)
                    self.root.iconphoto(False, photo)
        except Exception as e:
            log_error("ICON", icon_to_log, f"Could not set icon: {e}")


def main():
    root = tk.Tk()
    app = StockQuoteGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
