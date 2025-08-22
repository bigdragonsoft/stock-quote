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
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# 禁用 InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
  -idx, --indexes  显示指数列表而不是自选股
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
  按 'x' 键在自选股与指数显示间切换
  按 Ctrl+C 也可以退出程序
    """
    print(help_text)


def display_version():
    """
    显示程序版本和版权信息
    """
    version_text = """股票行情查看器

版本: 1.1
作者: GuoQiang
版权: Copyright (c) 2025 BigDragonSoft

这是一个命令行和图形界面的股票、外汇和加密货币报价查看工具。它可以从雪球获取股票数据，从东方财富网获取外汇数据，从528btc获取加密货币数据，并在终端或图形界面中以表格形式展示。

项目地址: https://github.com/bigdragonsoft/stock-quote
"""
    print(version_text)


def is_forex_symbol(symbol):
    """
    判断是否为外汇符号
    外汇符号格式如: USDCNH, USDJPY, EURUSD 等
    """
    # 首先检查是否在支持的外汇代码映射表中
    if symbol.upper() in forex_code_map:
        return True
    # 如果不在映射表中，使用正则表达式进行通用检查
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
            error_message = f"无法解析 {symbol} 的价格信息"
            log_error(symbol, html_content, error_message)
            return {"error": "ParsingError", "message": error_message}
        
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
            "Symbol": symbol,
            "Name": crypto_mapping[symbol]['name'],
            "Price": price,
            "Change": change,
            "Percent": f"{percent:.2f}%"
        }
        
        return crypto_info
        
    except requests.exceptions.RequestException as e:
        error_message = f"网络连接失败: {e}"
        log_error(symbol, "", error_message)
        return {"error": "NetworkError", "message": error_message}
    except (ValueError, AttributeError) as e:
        error_message = f"解析数据失败: {e}"
        log_error(symbol, html_content, error_message)
        return {"error": "ParsingError", "message": error_message}
    except Exception as e:
        error_message = f"发生未知错误: {e}"
        log_error(symbol, html_content, error_message)
        return {"error": "UnexpectedError", "message": error_message}


# 外汇代码映射表
forex_code_map = {
    'JPYUSD': {'secid': '119.JPYUSD', 'name': '日元/美元'},
    'USDCNH': {'secid': '133.USDCNH', 'name': '美元/人民币'},
    'EURUSD': {'secid': '119.EURUSD', 'name': '欧元/美元'},
    'GBPUSD': {'secid': '119.GBPUSD', 'name': '英镑/美元'},
    'AUDUSD': {'secid': '119.AUDUSD', 'name': '澳元/美元'},
    'USDJPY': {'secid': '119.USDJPY', 'name': '美元/日元'}
}

def get_eastmoney_forex_info(symbol):
    """
    从东方财富网获取外汇信息
    支持映射表中的外汇代码和通用的6位外汇代码
    """
    try:
        symbol = symbol.upper()
        
        # 获取对应的secid
        if symbol in forex_code_map:
            # 使用预定义的secid
            secid = forex_code_map[symbol]['secid']
            name = forex_code_map[symbol]['name']
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
                "Symbol": symbol,
                "Name": name,
                "Price": current_price,
                "Change": change_amount,
                "Percent": f"{change_percent:.2f}%" if change_percent is not None else "0.00%"
            }
            
            return forex_info
        else:
            # 如果不在映射表中且东方财富网没有数据，返回错误
            error_message = f"未能获取到有效的数据: {symbol}"
            log_error(symbol, str(data), error_message)
            return {"error": "ParsingError", "message": error_message}
            
    except requests.exceptions.RequestException as e:
        error_message = f"网络连接失败: {e}"
        log_error(symbol, "", error_message)
        return {"error": "NetworkError", "message": error_message}
    except json.JSONDecodeError as e:
        error_message = f"解析JSON数据失败: {e}"
        log_error(symbol, "", error_message)
        return {"error": "ParsingError", "message": error_message}
    except Exception as e:
        error_message = f"发生未知错误: {e}"
        log_error(symbol, "", error_message)
        return {"error": "UnexpectedError", "message": error_message}

def get_forex_info(symbol):
    """
    获取外汇信息，使用东方财富网API
    """
    return get_eastmoney_forex_info(symbol)


def get_stock_info(session, symbol, headers):
    """
    从雪球获取并显示股票信息。
    使用传入的 session 和 headers。
    """
    # 关键步骤：在请求 API 之前，先访问一次股票页面，以获取必要的 cookie
    session.get(f"https://xueqiu.com/S/{symbol}", headers=headers, verify=False)

    url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail"
    
    api_headers = headers.copy()
    api_headers.update({
        "Host": "stock.xueqiu.com",
        "Referer": f"https://xueqiu.com/S/{symbol}"
    })

    response_text = ""
    try:
        # 增加 verify=False 来绕过 SSL 验证
        response = session.get(url, headers=api_headers, verify=False)
        response_text = response.text
        response.raise_for_status()

        data = response.json()
        
        quote = data.get("data", {}).get("quote", {})
        
        if not quote:
            error_message = f"Could not find quote information for symbol: {symbol}"
            log_error(symbol, response_text, error_message)
            return {"error": "ParsingError", "message": error_message}

        name = quote.get("name")
        current_price = quote.get("current")
        change = quote.get("chg")
        percent_change = quote.get("percent")
        
        stock_info = {
            "Symbol": symbol,
            "Name": name,
            "Price": current_price,
            "Change": change,
            "Percent": f"{percent_change:.2f}%"
        }
        
        # Add extended hours data if available (for US stocks)
        if quote.get("current_ext") is not None:
            stock_info["extPrice"] = quote.get("current_ext")
            stock_info["extChange"] = quote.get("chg_ext")
            stock_info["extPercent"] = f'{quote.get("percent_ext"):.2f}%'
 
        return stock_info

    except requests.exceptions.RequestException as e:
        # 返回特定的错误信息
        error_message = f"Network connection failed: {e}"
        log_error(symbol, "", error_message)
        return {"error": "NetworkError", "message": error_message}
    except json.JSONDecodeError:
        error_message = "Failed to parse JSON response."
        log_error(symbol, response_text, error_message)
        return {"error": "ParsingError", "message": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        log_error(symbol, response_text, error_message)
        return {"error": "UnexpectedError", "message": error_message}


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


def load_indexes():
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
            save_indexes(default_indexes)
            return default_indexes
    except Exception as e:
        print(f"加载指数文件时出错: {e}")
        return []


def save_indexes(indexes):
    """
    将指数列表保存到文件
    """
    indexes_file = os.path.join(os.path.dirname(__file__), 'indexes.json')
    try:
        with open(indexes_file, 'w', encoding='utf-8') as f:
            json.dump({'indexes': indexes}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存指数文件时出错: {e}")


def display_stock_table(stock_data):
    """
    Takes a list of stock info dictionaries and prints a formatted table.
    """
    if not stock_data:
        return

    # Check if any stock has extended data to decide if we need the extra columns.
    has_ext_data = any("extPrice" in d for d in stock_data)
    
    headers = ["Symbol", "Price", "Change", "Percent"]
    if has_ext_data:
        headers.extend(["extPrice", "extChange", "extPercent"])
        
    # Create a header dict for tabulate to ensure column order and naming.
    header_map = {h: h for h in headers}
    
    display_data = [{k: v for k, v in d.items() if k != 'Name' and k != 'Note'} for d in stock_data]

    table = tabulate.tabulate(display_data, headers=header_map, tablefmt="grid")
    print(table)


def display_favorite_stocks(session, headers, favorites=None):
    """
    显示自选股的报价
    """
    if favorites is None:
        favorites = load_favorites()
    
    all_stock_info = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {}
        for symbol in favorites:
            if is_crypto_symbol(symbol):
                future = executor.submit(get_crypto_info, symbol)
            elif is_forex_symbol(symbol):
                future = executor.submit(get_forex_info, symbol)
            else:
                future = executor.submit(get_stock_info, session, symbol, headers)
            future_to_symbol[future] = symbol

        for future in as_completed(future_to_symbol):
            try:
                stock_info = future.result()
                if stock_info and not stock_info.get("error"):
                    all_stock_info.append(stock_info)
                elif stock_info and stock_info.get("error"):
                    pass
            except Exception as e:
                symbol = future_to_symbol[future]
                log_error(symbol, "", f"获取 {symbol} 数据时出错: {e}")

    # 按原始顺序排序结果
    symbol_order = {symbol: i for i, symbol in enumerate(favorites)}
    all_stock_info.sort(key=lambda x: symbol_order.get(x.get('Symbol'), float('inf')))

    display_stock_table(all_stock_info)


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        display_help()
        sys.exit(0)
    elif "-v" in sys.argv or "--version" in sys.argv:
        display_version()
        sys.exit(0)

    show_indexes = "-idx" in sys.argv or "--indexes" in sys.argv
    
    # 创建全局唯一的 Session 和 headers
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    # 第一次访问以获取 cookie
    session.get("https://xueqiu.com", headers=headers, verify=False)

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
            elif sys.argv[i] in ["-h", "--help", "-v", "--version", "-idx", "--indexes"]:
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
        
        running = True
        while running:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            if len(stock_symbols) > 0 and not show_indexes:
                all_stock_info = []
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_symbol = {}
                    for symbol in stock_symbols:
                        if is_crypto_symbol(symbol):
                            future = executor.submit(get_crypto_info, symbol)
                        elif is_forex_symbol(symbol):
                            future = executor.submit(get_forex_info, symbol)
                        else:
                            future = executor.submit(get_stock_info, session, symbol, headers)
                        future_to_symbol[future] = symbol

                    for future in as_completed(future_to_symbol):
                        try:
                            stock_info = future.result()
                            if stock_info and not stock_info.get("error"):
                                all_stock_info.append(stock_info)
                            elif stock_info and stock_info.get("error"):
                                pass
                        except Exception as e:
                            symbol = future_to_symbol[future]
                            log_error(symbol, "", f"获取 {symbol} 数据时出错: {e}")

                # 按原始顺序排序结果
                symbol_order = {symbol: i for i, symbol in enumerate(stock_symbols)}
                all_stock_info.sort(key=lambda x: symbol_order.get(x.get('Symbol'), float('inf')))

                if not all_stock_info:
                    print("错误: 输入的代码为无效代码，请检查后重新输入。")
                    sys.exit(1)
                
                display_stock_table(all_stock_info)

            else:
                if show_indexes:
                    indexes = load_indexes()
                    display_favorite_stocks(session, headers, favorites=indexes)
                else:
                    display_favorite_stocks(session, headers)
        
            print(f"\n")

            start_time = time.time()
            timeout = refresh_interval
            while time.time() - start_time < timeout:
                elapsed_time = time.time() - start_time
                remaining_time = int(timeout - elapsed_time)
                
                # 输出剩余时间，'\r' 表示回到行首，end='' 防止换行
                print(f"\r按 'Q' 退出，按 'X' 切换自选/指数，或等待 {remaining_time} 秒后自动刷新...", end='', flush=True)
                
                if keyboard.has_input():
                    char = keyboard.get_input()
                    if char == 'q':
                        print("\n\n退出程序...")
                        running = False
                        break
                    elif char == 'x':
                        show_indexes = not show_indexes
                        break
                time.sleep(0.1)
            # 在刷新前清除剩余时间显示
            print("\r" + " " * 30 + "\r", end='', flush=True)
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，退出程序...")
        sys.exit(0)
    finally:
        keyboard.stop()  # 确保退出时恢复终端设置
