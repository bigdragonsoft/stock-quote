import requests
import json
import os
import sys
import time
import tabulate
import select
import sys
import threading
import queue
import platform
import re


class KeyboardInput:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._input_listener, daemon=True)
        self.original_settings = None  # 存储原始终端设置
        self.thread.start()

    def _input_listener(self):
        if platform.system() == 'Windows':
            import msvcrt
            while self.running:
                if msvcrt.kbhit():
                    char = msvcrt.getch().decode('utf-8').lower()
                    self.input_queue.put(char)
                    if char == 'q':
                        self.running = False
        else:
            import sys, termios
            import tty
            self.original_settings = termios.tcgetattr(sys.stdin)  # 保存原始设置
            try:
                tty.setcbreak(sys.stdin.fileno())
                while self.running:
                    try:
                        char = sys.stdin.read(1).lower()
                        self.input_queue.put(char)
                        if char == 'q':
                            self.running = False
                    except Exception as e:
                        print(f"输入监听错误: {e}")
            finally:
                # 确保恢复终端设置
                if sys.stdin.isatty() and self.original_settings:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)

    def stop(self):
        """清理资源"""
        self.running = False
        if not platform.system() == 'Windows' and sys.stdin.isatty():
            import termios
            # 确保最终恢复终端设置
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)
            except:
                pass

    def has_input(self):
        return not self.input_queue.empty()

    def get_input(self):
        return self.input_queue.get_nowait()


def display_help():
    """
    显示程序帮助信息
    """
    help_text = """
用法: python stock_quote.py [选项] [股票代码...]

选项:
  -i <秒数>        指定刷新间隔秒数，默认为30秒
  -h, --help       显示此帮助信息并退出
  -v, --version    显示版本信息

示例:
  python stock_quote.py              使用默认自选股并每30秒刷新
  python stock_quote.py SH513100     查看指定股票并每30秒刷新
  python stock_quote.py -i 10 SH513100 SH513500    每10秒刷新查看两个股票
  python stock_quote.py USDJPY      查看美元兑日元汇率
  python stock_quote.py BTC         查看比特币价格
  python stock_quote.py ETH         查看以太坊价格
  python stock_quote.py -h           显示此帮助信息

在程序运行过程中:
  按 'q' 键退出程序
  按 Ctrl+C 也可以退出程序
    """
    print(help_text)


def display_version():
    """
    显示程序版本和版权信息
    """
    version_text = """股票行情查看器

版本: 1.0
作者: GuoQiang
版权: Copyright (c) 2025

这是一个命令行和图形界面的股票、外汇和加密货币报价查看工具。它可以从雪球获取股票数据，从新浪财经获取外汇数据，从528btc获取加密货币数据，并在终端或图形界面中以表格形式展示。

项目地址: https://github.com/bigdragonsoft/stock-quote
"""
    print(version_text)


def is_forex_symbol(symbol):
    """
    判断是否为外汇符号
    外汇符号格式如: USDCNH, USDJPY, EURUSD 等
    """
    # 外汇代码通常是6个字母组成，前3个是基础货币，后3个是报价货币
    return bool(re.match(r'^[A-Z]{6}$', symbol)) and symbol != "SH513100" and symbol != "SH513500" and symbol != "SH513180" and symbol != "IBIT"


def is_crypto_symbol(symbol):
    """
    判断是否为加密货币符号
    """
    crypto_symbols = ['BTC', 'ETH', 'XRP', 'USDT', 'BNB', 'SOL', 'USDC', 'DOGE', 'ADA', 'SHIB']
    return symbol.upper() in crypto_symbols


def get_crypto_info(symbol):
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
        return {"error": "InvalidSymbol", "message": f"不支持的加密货币: {symbol}"}
    
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
            return {"error": "ParsingError", "message": f"无法解析 {symbol} 的价格信息"}
        
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
            "Symbol": symbol,
            "Name": crypto_mapping[symbol]['name'],
            "Price": price,
            "Change": change,
            "Percent": f"{percent:.2f}%"
        }
        
        return crypto_info
        
    except requests.exceptions.RequestException as e:
        return {"error": "NetworkError", "message": f"网络连接失败: {e}"}
    except (ValueError, AttributeError) as e:
        return {"error": "ParsingError", "message": f"解析数据失败: {e}"}
    except Exception as e:
        return {"error": "UnexpectedError", "message": f"发生未知错误: {e}"}


def get_forex_info(symbol):
    """
    从新浪财经获取外汇信息
    """
    try:
        # 转换 symbol 格式, e.g., USDJPY -> fx_susdjpy
        if len(symbol) == 6:
            formatted_symbol = f"fx_s{symbol.lower()}"
        else:
            # 如果格式不正确，直接返回
            return {"error": "InvalidSymbol", "message": f"Invalid forex symbol format: {symbol}"}

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
            return {"error": "ParsingError", "message": f"Failed to parse data from sina for {symbol}"}
        
        # 提取数据部分
        data_content = data_str.split('"')[1]
        data_fields = data_content.split(',')
        
        if len(data_fields) < 15:
            return {"error": "ParsingError", "message": f"Insufficient data from sina for {symbol}"}
        
        #print(data_fields)  # 调试输出完整数据字段
        #exit()

        # 提取关键信息
        price = float(data_fields[8]) if data_fields[8] else 0  # 现汇买入价
        change = float(data_fields[11]) if data_fields[11] else 0  # 涨跌额
        # 使用现钞买入价作为基准计算涨跌百分比
        base_price = float(data_fields[3]) if data_fields[3] else 1
        change_percent = (change / base_price * 100) if base_price != 0 else 0
        
        forex_info = {
            "Symbol": symbol,
            "Name": data_fields[9],  # 货币名称
            "Price": price,
            "Change": change,
            "Percent": f"{change_percent:.4f}%"
        }
        
        return forex_info
        
    except requests.exceptions.RequestException as e:
        return {"error": "NetworkError", "message": f"Network connection failed for {symbol}: {e}"}
    except (AttributeError, ValueError, IndexError) as e:
        # Handle cases where selectors don't find the element or conversion fails
        return {"error": "ParsingError", "message": f"Failed to parse data from sina for {symbol}. The site structure may have changed."}
    except Exception as e:
        return {"error": "UnexpectedError", "message": f"An unexpected error occurred for {symbol}: {e}"}


def get_stock_info(symbol):
    """
    从雪球获取并显示股票信息。
    """
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    session.get(f"https://xueqiu.com/S/{symbol}", headers=headers)

    url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail"
    
    api_headers = headers.copy()
    api_headers.update({
        "Host": "stock.xueqiu.com",
        "Referer": f"https://xueqiu.com/S/{symbol}"
    })

    try:
        response = session.get(url, headers=api_headers)
        response.raise_for_status()  

        data = response.json()
        
        quote = data.get("data", {}).get("quote", {})
        
        if not quote:
            print(f"Could not find quote information for symbol: {symbol}")
            print("Response from server:", response.text)
            return None

        name = quote.get("name")
        current_price = quote.get("current")
        change = quote.get("chg")
        percent_change = quote.get("percent")
        
        stock_info = {
            "Symbol": symbol,
            "Name": name,
            "Price": current_price,
            "Change": change,
            "Percent": f"{percent_change}%"
        }
 
        return stock_info

    except requests.exceptions.RequestException as e:
        # 返回特定的错误信息
        return {"error": "NetworkError", "message": f"Network connection failed: {e}"}
    except json.JSONDecodeError:
        print("Failed to parse JSON response.")
        print("Response from server:", response.text)
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def load_favorites():
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
            save_favorites(default_favorites)
            return default_favorites
    except Exception as e:
        print(f"加载自选股文件时出错: {e}")
        return ["SH513100", "SH513500", "SH513180", "IBIT"]


def save_favorites(favorites):
    """
    将自选股列表保存到文件
    """
    favorites_file = os.path.join(os.path.dirname(__file__), 'favorites.json')
    try:
        with open(favorites_file, 'w', encoding='utf-8') as f:
            json.dump({'stocks': favorites}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存自选股文件时出错: {e}")


def display_favorite_stocks(favorites=None):
    """
    显示自选股的报价
    """
    if favorites is None:
        favorites = load_favorites()
    
    all_stock_info = []
    forex_notes = []
    for symbol in favorites:
        # 判断是否为加密货币
        if is_crypto_symbol(symbol):
            stock_info = get_crypto_info(symbol)
        # 判断是否为外汇
        elif is_forex_symbol(symbol):
            stock_info = get_forex_info(symbol)
            # 收集外汇提示信息
            if stock_info and "Note" in stock_info:
                forex_notes.append(f"{symbol}: {stock_info['Note']}")
        else:
            stock_info = get_stock_info(symbol)
            
        if stock_info:
            all_stock_info.append(stock_info)
    
    display_data = [{k: v for k, v in d.items() if k != 'Name' and k != 'Note'} for d in all_stock_info]
    table = tabulate.tabulate(display_data, headers="keys", tablefmt="grid")
    print(table)
    
    # 打印外汇提示信息
    if forex_notes:
        print("\n注意:")
        for note in forex_notes:
            print(f"  {note}")


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        display_help()
        sys.exit(0)
    elif "-v" in sys.argv or "--version" in sys.argv:
        display_version()
        sys.exit(0)
    
    keyboard = KeyboardInput()  # 初始化跨平台输入检测
    try:
        refresh_interval = 30  # 默认刷新间隔为30秒
        stock_symbols = []
        
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "-i" and i + 1 < len(sys.argv):
                try:
                    refresh_interval = int(sys.argv[i + 1])
                    i += 2  # 跳过 -i 和它的参数值
                except ValueError:
                    print("错误: -i 参数需要一个整数值")
                    sys.exit(1)
            elif sys.argv[i] in ["-h", "--help"]:
                i += 1
            elif sys.argv[i].startswith("-"):
                # 处理未知参数
                print(f"错误: 未知参数 '{sys.argv[i]}'")
                display_help()
                sys.exit(1)
            else:
                # 将股票代码转换为大写
                stock_symbols.append(sys.argv[i].upper())
                i += 1
        
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            if len(stock_symbols) > 0:
                all_stock_info = []
                forex_notes = []
                for stock_symbol in stock_symbols:
                    # 判断是否为加密货币
                    if is_crypto_symbol(stock_symbol):
                        stock_info = get_crypto_info(stock_symbol)
                    # 判断是否为外汇
                    elif is_forex_symbol(stock_symbol):
                        stock_info = get_forex_info(stock_symbol)
                        # 收集外汇提示信息
                        if stock_info and "Note" in stock_info:
                            forex_notes.append(f"{stock_symbol}: {stock_info['Note']}")
                    else:
                        stock_info = get_stock_info(stock_symbol)
                        
                    # 检查是否有错误信息
                    if stock_info is None or (isinstance(stock_info, dict) and "error" in stock_info):
                        # 显示错误信息并退出程序
                        if stock_info and "message" in stock_info:
                            print(stock_info["message"])
                        elif stock_info is None:
                            print(f"无法获取 {stock_symbol} 的数据")
                        else:
                            print(f"无法获取 {stock_symbol} 的数据")
                        sys.exit(1)
                    elif stock_info:
                        all_stock_info.append(stock_info)

                if all_stock_info:
                    display_data = [{k: v for k, v in d.items() if k != 'Name' and k != 'Note'} for d in all_stock_info]
                    table = tabulate.tabulate(display_data, headers="keys", tablefmt="grid")
                    print(table)
                    
                    # 打印外汇提示信息
                    if forex_notes:
                        print("\n注意:")
                        for note in forex_notes:
                            print(f"  {note}")

            else:
                display_favorite_stocks()
        
            print(f"\n")

            start_time = time.time()
            timeout = refresh_interval
            while time.time() - start_time < timeout:
                elapsed_time = time.time() - start_time
                remaining_time = int(timeout - elapsed_time)
                
                # 输出剩余时间，'\r' 表示回到行首，end='' 防止换行
                print(f"\r按 'Q' 键退出，或等待 {remaining_time} 秒后自动刷新...", end='', flush=True)
                
                if keyboard.has_input():
                    char = keyboard.get_input()
                    if char == 'q':
                        print("\n\n退出程序...")
                        exit()
                time.sleep(0.1)
            # 在刷新前清除剩余时间显示
            print("\r" + " " * 30 + "\r", end='', flush=True)
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，退出程序...")
        sys.exit(0)
    finally:
        keyboard.stop()  # 确保退出时恢复终端设置
