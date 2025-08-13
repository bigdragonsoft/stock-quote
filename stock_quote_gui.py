import requests
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

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
        self.root.title("Stock-Quote 股票行情查看器")
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
        
        # 刷新间隔（秒）
        self.refresh_interval = 30
        
        # 控制刷新的标志
        self.refresh_active = False
        self.last_refresh_time = time.time()
        
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
        about_text = """股票行情查看器

版本: 1.0
作者: GuoQiang
版权: Copyright (c) 2025

这是一个命令行和图形界面的股票、外汇和加密货币报价查看工具。它可以从雪球获取股票数据，从新浪财经获取外汇数据，从528btc获取加密货币数据，并在图形界面中以表格形式展示。

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
        
        # 编辑按钮
        self.edit_button = ttk.Button(control_frame, text="管理股票", command=self.toggle_edit_frame)
        self.edit_button.pack(side=tk.LEFT)
        
        # 自选股按钮
        self.favorites_button = ttk.Button(control_frame, text="显示自选股", command=self.show_favorites)
        self.favorites_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 指数按钮
        self.indexes_button = ttk.Button(control_frame, text="显示指数", command=self.show_indexes)
        self.indexes_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 刷新间隔设置
        ttk.Label(control_frame, text="刷新间隔(秒):").pack(side=tk.LEFT, padx=(10, 5))
        self.interval_var = tk.StringVar(value=str(self.refresh_interval))
        interval_spinbox = ttk.Spinbox(control_frame, from_=5, to=300, width=5, 
                                      textvariable=self.interval_var, 
                                      command=self.update_interval)
        interval_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        # 绑定回车键事件，使输入后按回车也能更新时间间隔
        interval_spinbox.bind('<Return>', lambda event: self.update_interval())
        
        # 开始/停止刷新按钮
        self.toggle_button = ttk.Button(control_frame, text="停止刷新", command=self.toggle_refresh)
        self.toggle_button.pack(side=tk.RIGHT)
        
        # 手动刷新按钮
        refresh_button = ttk.Button(control_frame, text="刷新", command=self.load_stock_data)
        refresh_button.pack(side=tk.RIGHT, padx=(0, 10))
        
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

    def is_forex_symbol(self, symbol):
        """
        判断是否为外汇符号
        外汇符号格式如: USDCNH, USDJPY, EURUSD 等
        """
        # 外汇代码通常是6个字母组成，前3个是基础货币，后3个是报价货币
        return bool(re.match(r'^[A-Z]{6}$', symbol))
    
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
            percent_match = re.search(r'<div id="rise_fall_percent"[^>]*>\+?([0-9]+\.?[0-9]*)\s*%', html_content)
            
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
                percent = float(percent_match.group(1))
                
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

    def get_forex_info(self, symbol):
        """
        从新浪财经获取外汇信息
        """
        data_str = ""
        try:
            # 转换 symbol 格式, e.g., USDJPY -> fx_susdjpy
            if len(symbol) == 6:
                formatted_symbol = f"fx_s{symbol.lower()}"
            else:
                # 如果格式不正确，直接返回
                return None

            url = f"https://hq.sinajs.cn/list={formatted_symbol}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://finance.sina.com.cn"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # 解析返回的数据
            # 格式: var hq_str_fx_susdjpy="..."
            data_str = response.text.strip()
            if not data_str.startswith("var"):
                log_error(symbol, data_str, "Failed to parse data from sina")
                return None
            
            # 提取数据部分
            data_content = data_str.split('"')[1]
            data_fields = data_content.split(',')
            
            if len(data_fields) < 15:
                log_error(symbol, data_content, "Insufficient data from sina")
                return None
            
            # 提取关键信息
            price = float(data_fields[8]) if data_fields[8] else 0  # 现汇买入价
            change = float(data_fields[11]) if data_fields[11] else 0  # 涨跌额
            # 使用现钞买入价作为基准计算涨跌百分比
            base_price = float(data_fields[3]) if data_fields[3] else 1
            change_percent = (change / base_price * 100) if base_price != 0 else 0
            
            forex_info = {
                "Region": "FX",
                "Status": "-",
                "Name": data_fields[9],  # 货币名称
                "Symbol": symbol,
                "Price": price,
                "Change": change,
                "Percent": f"{change_percent:.4f}%"  # 保留小数点后4位
            }
            
            return forex_info
            
        except requests.exceptions.RequestException as e:
            log_error(symbol, "", f"Request error: {e}")
            return None
        except (AttributeError, ValueError, IndexError) as e:
            log_error(symbol, data_str, f"Parsing error: {e}")
            return None
        except Exception as e:
            log_error(symbol, data_str, f"Unknown error: {e}")
            return None
    
    def get_stock_info(self, symbol):
        """
        从雪球获取股票信息
        """
        # 判断是否为加密货币
        if self.is_crypto_symbol(symbol):
            return self.get_crypto_info(symbol)
        
        # 判断是否为外汇
        if self.is_forex_symbol(symbol):
            return self.get_forex_info(symbol)
        
        response_text = ""
        try:
            # 为了获取必要的 cookie，我们首先访问股票页面
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
            }
            self.session.get(f"https://xueqiu.com/S/{symbol}", headers=headers)

            url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail"
            
            # 添加 API 请求头
            api_headers = headers.copy()
            api_headers.update({
                "Host": "stock.xueqiu.com",
                "Referer": f"https://xueqiu.com/S/{symbol}"
            })

            # 发起 API 请求
            response = self.session.get(url, headers=api_headers)
            response_text = response.text
            response.raise_for_status()

            data = response.json()
            quote = data.get("data", {}).get("quote", {})
            market = data.get("data", {}).get("market", {})
            
            if not quote:
                log_error(symbol, response_text, "Could not find quote information")
                return None

            # 收集股票信息
            stock_info = {
                "Region": market.get("region", "未知"),
                "Status": market.get("status", "未知"),
                "Name": quote.get("name", "未知"),
                "Symbol": symbol,
                "Price": quote.get("current"),
                "Change": quote.get("chg"),
                "Percent": f"{quote.get('percent')}%"
            }
            
            return stock_info

        except requests.exceptions.RequestException as e:
            log_error(symbol, "", f"Request error: {e}")
            return None
        except json.JSONDecodeError:
            log_error(symbol, response_text, "JSON parsing error")
            return None
        except Exception as e:
            log_error(symbol, response_text, f"Unknown error: {e}")
            return None
    
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
            # 在主线程中更新GUI
            self.root.after(0, self.update_gui_with_data, [])
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

        # 在主线程中更新GUI
        self.root.after(0, self.update_gui_with_data, all_stock_info)

    def update_gui_with_data(self, all_stock_info):
        """
        用获取到的数据更新GUI（在主线程中运行）
        """
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
                data_values = [stock.get('Region', '-'), status_display, stock.get('Symbol', '-'), 
                              stock.get('Price', '-'), stock.get('Change', '-'), stock.get('Percent', '-'), stock.get('Name', '-')]
                
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
        self.load_stock_data()
        
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
        self.load_stock_data()
        
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
    
    def on_closing(self):
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
        # 尝试设置图标，支持多种可能的图标文件名
        icon_files = ['icon.ico', 'stock_icon.ico', 'app_icon.ico', 'favicon.ico']
        for icon_file in icon_files:
            icon_path = os.path.join(os.path.dirname(__file__), icon_file)
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                    break
                except Exception as e:
                    log_error("ICON", icon_file, f"Could not set icon: {e}")
                    continue


def main():
    root = tk.Tk()
    app = StockQuoteGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
