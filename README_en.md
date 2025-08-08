[中文版本](README.md)

# Stock, Forex, and Cryptocurrency Quote Tool

This is a command-line and graphical interface tool for viewing stock, forex, and cryptocurrency quotes. It retrieves stock data from Xueqiu, forex data from Sina Finance, and cryptocurrency data from 528btc, displaying them in tabular form in either the terminal or graphical interface.

This software is primarily designed for users who don't want to open trading software or browse web pages to check market quotes. Through a simple terminal or graphical interface, users can quickly obtain the required market information without the hassle of opening heavy trading software or browsing the web.

## Features

- **Real-time Data**: Obtain real-time quotes for stocks, forex, and cryptocurrencies.
- **Dual Interface Support**: Provides both command-line interface and graphical user interface.
- **Multiple Code Support**: Supports various stock codes (A-shares, Hong Kong stocks, US stocks), major forex pairs (such as USDJPY, USDCNY), and cryptocurrencies (such as BTC, ETH).
- **Customizable Refresh Rate**: Customize the data refresh interval.
- **Default Watchlist**: Displays a preset watchlist when run without parameters.
- **Cross-platform**: Supports Windows, macOS, and Linux systems.

## Screenshots

### Command-Line Interface
```
+----------+-------------+----------+-----------+
| Symbol   |       Price |   Change | Percent   |
+==========+=============+==========+===========+
| SH513100 |      1.691  |   0.007  | 0.42%     |
+----------+-------------+----------+-----------+
| SH513500 |      2.174  |   0      | 0.0%      |
+----------+-------------+----------+-----------+
| SH513180 |      0.738  |  -0.012  | -1.6%     |
+----------+-------------+----------+-----------+
| IBIT     |     66.83   |   1.32   | 2.015%    |
+----------+-------------+----------+-----------+
| USDCNH   |      7.1896 |   0.0096 | 0.1337%   |
+----------+-------------+----------+-----------+
| BTC      | 116577      | 186.23   | 0.16%     |
+----------+-------------+----------+-----------+
| 03032    |      5.445  |  -0.08   | -1.45%    |
+----------+-------------+----------+-----------+

按 'Q' 键退出，或等待 25 秒后自动刷新...
```

### Graphical User Interface
<img src="screenshot_gui.png" width="60%">

## Installation

1. Clone or download this repository to your local machine.
2. Ensure you have Python 3 installed.
3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Command Line Interface

Run the `stock_quote.py` script via command line.

#### Basic Usage

```bash
python stock_quote.py [options] [stock/forex/cryptocurrency codes...]
```

#### Options

- `-i <seconds>`: Specify the refresh interval in seconds, default is 30 seconds.
- `-h`, `--help`: Display help information.
- `-v`, `--version`: Display version information.

#### Examples

- **View default watchlist** (refresh every 30 seconds):
    ```bash
    python stock_quote.py
    ```

- **View specific stock** (e.g., Nasdaq 100 ETF):
    ```bash
    python stock_quote.py SH513100
    ```

- **View multiple stocks with 10-second refresh interval**:
    ```bash
    python stock_quote.py -i 10 SH513100 SH513500
    ```

- **View forex rate** (e.g., USD to JPY):
    ```bash
    python stock_quote.py USDJPY
    ```

- **View cryptocurrency price** (e.g., Bitcoin):
    ```bash
    python stock_quote.py BTC
    ```

- **View stocks, forex, and cryptocurrencies simultaneously**:
    ```bash
    python stock_quote.py SH513100 USDJPY BTC ETH
    ```

#### Interaction

- Press `q` key to exit the program at any time during runtime.
- Press `Ctrl+C` to terminate the program.

### Graphical User Interface

Start the graphical interface version by running the `stock_quote_gui.py` script:

```bash
python stock_quote_gui.py
```

The graphical interface provides richer interactive features:
- Visual management of watchlists (supports stocks, forex, and cryptocurrencies)
- Real-time and manual refresh control
- Adjustable refresh interval
- Scrollable table for displaying large amounts of data
- Status bar showing update time and countdown

In the graphical interface, you can add cryptocurrency codes (such as BTC, ETH) to the watchlist through the "Manage Stocks" function.

## Program Packaging and Distribution

For convenience, you can package the program as an executable file, which can run on computers without Python installed.

### Packaging with PyInstaller

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Package the command-line version:
   ```bash
   pyinstaller --onefile stock_quote.py
   ```
   
3. Package the graphical interface version:
   ```bash
   pyinstaller --onefile --windowed stock_quote_gui.py
   ```

4. After packaging, the executable file will be located in the `dist` directory.

### Packaging Parameter Description

- `--onefile`: Package all dependencies into a single executable file
- `--windowed`: For GUI applications, avoid displaying the console window (Windows and macOS)
- `--icon=icon.ico`: Specify the icon for the executable file (requires .ico format icon file)
- `--name=StockQuote`: Specify the name of the generated executable file

### Custom Packaging Examples

```bash
# Package command-line version with custom icon and name
pyinstaller --onefile --name=StockQuoteCLI --icon=icon.ico stock_quote.py

# Package graphical interface version with custom icon and name
pyinstaller --onefile --windowed --name=StockQuoteGUI --icon=icon.ico stock_quote_gui.py
```

### Notes

1. The packaged file may be flagged by antivirus software, which is normal as the file structure of PyInstaller packaged files may be misjudged
2. The packaging process may take some time, especially the first time
3. The generated executable file may be large (typically 50-100MB) because it includes the Python interpreter and all dependencies
4. If you need a smaller file size, consider using a virtual environment with only necessary dependencies installed before packaging

## Supported Cryptocurrencies

The current version supports the following cryptocurrencies:
- BTC (Bitcoin)
- ETH (Ethereum)
- XRP (Ripple)
- USDT (Tether)
- BNB (Binance Coin)
- SOL (Solana)
- USDC (USD Coin)
- DOGE (Dogecoin)
- ADA (Cardano)
- SHIB (Shiba Inu)

## Data Sources

- **Stock Data**: From Xueqiu (xueqiu.com)
- **Forex Data**: From Sina Finance (finance.sina.com.cn)
- **Cryptocurrency Data**: From 528btc (528btc.com)

## Configuration File

The program uses the `favorites.json` file to store the watchlist. A default configuration file will be automatically created on first run.

## Dependencies

See the `requirements.txt` file for all dependencies.
