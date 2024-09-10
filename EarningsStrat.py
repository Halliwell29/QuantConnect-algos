#region imports
from AlgorithmImports import *
from QuantConnect.DataSource import *
from QuantConnect.Data.Market import TradeBar, QuoteBar
from QuantConnect.DataSource import EstimizeConsensus, EstimizeEstimate, EstimizeRelease
from QuantConnect.Data.Consolidators import TradeBarConsolidator
import numpy as np
import pandas as pd
from datetime import timedelta
#endregion

class CombinedAlgorithm(QCAlgorithm):

    def Initialize(self):
        # Initialize
        self.SetStartDate(2022, 11, 1)
        self.SetEndDate(2023, 1, 1)
        self.SetCash(10000) 
        self.SPY = self.AddEquity('SPY', Resolution.Minute).Symbol
        self.SetWarmUp(timedelta(days=20))

        # Universe Selection
        self.AddUniverse(self.CoarseSelectionFunction)
        self.UniverseSettings.Resolution = Resolution.Minute

        # Scheduled Events
        self.Schedule.On(self.DateRules.EveryDay(),self.TimeRules.AfterMarketOpen(self.SPY),self.MarketOpen)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose(self.SPY, 3), self.LiquidateToggle)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose(self.SPY, 1), self.ResetWatchlist)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose(self.SPY), self.MarketClose)

        # Variables 
        self.Watchlist = []

        self.Tickerlist = ["AAPL", "AMD", "AMZN", "META", "TSLA", "GOOGL", "BBY", "DKNG", "GS", "DASH", "UBER", "ABNB", \
            "NFLX", "NVDA", "PYPL", "BYND", "MSFT", "BA", "AMAT", "HD", "FDX", "LOW", "CRWD", "CRM", "TRIP", \
                "TCOM", "BABA", "ADSK", "BILI", "AVGO", "CAT", "CHGG", "DXCM", "ENPH", "ETSY", "EXPE", "FSLR", \
                    "FAST", "FSLY", "GM", "GOOS", "GPS", "KMX", "LEVI", "LULU", "LUV", "LVS", "M", "MAR", "MRVL", "MTCH", \
                        "NIO", "NOW", "PENN", "PLUG", "PTON", "QRVO", "QCOM", "ROKU", "SE", "SHOP", "SBUX", "SNAP", \
                            "SPLK", "SPOT", "SPWR", "SQ", "SWKS", "TDOC", "TER", "TWLO", "TTD", "UPS", "URBN", "GME", \
                                "WDAY", "W", "WDC", "WYNN", "XPO", "ATVI", "WIX", "JD", "LYFT", "PINS", "DDOG", \
                                    "ORCL", "DOCU", "ZM", "UPST"]
                                    
        self.macdBySymbol = {}
        self.betaBySymbol = {}
        self.highs = {}
        self.lows = {}
        self.entry_price = {}
        self.trade_count = {}

        # Toggles 
        self.market_open = False
        self.liquidate = False

        self.long_entry = {symbol: False for symbol in self.Watchlist}
        self.short_entry = {symbol: False for symbol in self.Watchlist}
        
        self.first_dydx_sell = {symbol: False for symbol in self.Watchlist}
        self.signal_cross_check = {symbol: False for symbol in self.Watchlist}
        self.second_dydx_sell = {symbol: False for symbol in self.Watchlist}

        self.SetSecurityInitializer(lambda x: x.SetMarketPrice(self.GetLastKnownPrice(x)))
    
    def CoarseSelectionFunction(self, coarse):
        sorted_by_dollar_volume = sorted([x for x in coarse if x.HasFundamentalData and x.Price > 10 and x.Price < 500], 
                                key=lambda x: x.DollarVolume, reverse=True)
        selected = [x.Symbol for x in sorted_by_dollar_volume[:20]]

        return selected
    
    # SCHEDULED FUNCTIONS
    def MarketOpen(self):
        for symbol in self.Watchlist:
            self.highs[symbol] = []
            self.lows[symbol] = []
            self.entry_price[symbol] = []
            self.trade_count[symbol] = 0
            self.Log(symbol)
        self.market_open = True

        self.long_entry = {symbol: False for symbol in self.Watchlist}
        self.short_entry = {symbol: False for symbol in self.Watchlist}
        self.first_dydx_sell = {symbol: False for symbol in self.Watchlist}
        self.signal_cross_check = {symbol: False for symbol in self.Watchlist}
        self.second_dydx_sell = {symbol: False for symbol in self.Watchlist}
    
    def LiquidateToggle(self):
        self.liquidate = True

    def ResetWatchlist(self):
        self.Watchlist = []
        self.liquidate = False
    
    def MarketClose(self): 
        return

    def OnData(self, data): 
        if self.IsWarmingUp:
            return   

        # Accessing Data
        release = data.Get(EstimizeRelease)

        for key, value in release.items():
            for ticker in self.Tickerlist:
                if str(value.Symbol.Underlying) == ticker:
                    self.Watchlist.append(value.Symbol)
        
        for symbol in self.Watchlist:
           
            if not symbol.Value in [x.Value for x in self.macdBySymbol]:
                continue

            symbol_m =  [x for x in self.macdBySymbol if symbol.Value== x.Value][0]
            symbol_data = self.macdBySymbol[symbol_m]

            if symbol_data is None or not self.macdBySymbol[symbol_m].warmed_up or not symbol_data.warmed_up:
                continue

            # VARIABLES
            symbol_price = self.Securities[symbol_m].Price
            held_stocks = self.Portfolio[symbol_m].Quantity
            min_high = self.Securities[symbol_m].High
            min_low = self.Securities[symbol_m].Low

            prev_macd = symbol_data.prev_macd
            current_macd = symbol_data.current_macd
            prev_macd_slope = symbol_data.prev_macd_slope
            current_macd_slope = symbol_data.current_macd_slope
            current_signal = symbol_data.current_signal

            # Five Minute Range
            if symbol in self.highs and symbol in self.lows and len(self.highs[symbol]) < 5 and len(self.lows[symbol]) < 5:
                self.highs[symbol].append(min_high)
                self.lows[symbol].append(min_low)
            if symbol in self.highs and symbol in self.lows and len(self.highs[symbol]) == 5 and len(self.lows[symbol]) == 5:
                five_min_high = max(self.highs[symbol])
                five_min_low = min(self.lows[symbol])
                five_min_range = five_min_high - five_min_low

                # Long Trades 

                    # MACD > Signal / First Derivative 
                if (symbol_price > five_min_high) and (current_macd > current_signal) and self.trade_count[symbol] == 0:
                    cash_per_stock = int(self.Portfolio.Cash / 3)
                    shares_to_buy = int(cash_per_stock / self.Securities[symbol.Underlying].Price)
                    self.MarketOrder(symbol.Underlying, shares_to_buy)
                    self.entry_price[symbol] = symbol_price
                    self.first_dydx_sell[symbol] = True
                    self.long_entry[symbol] = True
                    self.trade_count[symbol] += 1 
                    self.Log(f"{symbol}: Long at {symbol_price} (MACD > Signal)")
                
                if symbol in self.long_entry and symbol in self.first_dydx_sell:
                    if self.long_entry[symbol] and self.first_dydx_sell[symbol] and (prev_macd_slope > 0) and (current_macd_slope <= 0):
                        self.Liquidate(symbol.Underlying)
                        self.first_dydx_sell[symbol] = False
                        self.long_entry[symbol] = False
                        self.Log(f"{symbol}: Exit long at {symbol_price} (MACD slope crosses zero)")
                    
                    if self.long_entry[symbol] and self.first_dydx_sell[symbol] and (symbol_price < (self.entry_price[symbol] * 0.99)):
                        self.Liquidate(symbol.Underlying)
                        self.first_dydx_sell[symbol] = False
                        self.long_entry[symbol] = False
                        self.Log(f"{symbol}: Exit long at {symbol_price} (Stopped out)")
                
                    # MACD < Signal / Second Derivative
                if (symbol_price > five_min_high) and (current_macd < current_signal) and self.trade_count[symbol] == 0:
                    cash_per_stock = int(self.Portfolio.Cash / 3)
                    shares_to_buy = int(cash_per_stock / self.Securities[symbol.Underlying].Price)
                    self.MarketOrder(symbol.Underlying, shares_to_buy)
                    self.entry_price[symbol] = symbol_price
                    self.signal_cross_check[symbol] = True  
                    self.long_entry[symbol] = True
                    self.trade_count[symbol] += 1  
                    self.Log(f"{symbol}: Long at {symbol_price} (MACD < Signal)")
                
                if symbol in self.long_entry and symbol in self.signal_cross_check and symbol in self.second_dydx_sell:
                    if self.long_entry[symbol] and self.signal_cross_check[symbol] and (current_macd > current_signal):
                        self.second_dydx_sell[symbol] = True
                    if self.long_entry[symbol] and self.second_dydx_sell[symbol] and (prev_macd_slope > current_macd_slope):
                        self.Liquidate(symbol.Underlying)
                        self.signal_cross_check[symbol] = False
                        self.second_dydx_sell[symbol] = False
                        self.long_entry[symbol] = False
                        self.Log(f"{symbol}: Exit long at {symbol_price} (MACD inflection point)")
                    
                    if self.long_entry[symbol] and self.signal_cross_check[symbol] and (symbol_price < (self.entry_price[symbol] * 0.99)):
                        self.Liquidate(symbol.Underlying)
                        self.signal_cross_check[symbol] = False
                        self.second_dydx_sell[symbol] = False
                        self.long_entry[symbol] = False
                        self.Log(f"{symbol}: Exit long at {symbol_price} (Stopped out)")
                
                # Short Trades

                    # MACD < Signal / First Derivative
                if (symbol_price < five_min_low) and (current_macd < current_signal) and self.trade_count[symbol] == 0:
                    cash_per_stock = int(self.Portfolio.Cash / 3)
                    shares_to_buy = int(cash_per_stock / self.Securities[symbol.Underlying].Price)
                    self.ticket = self.MarketOrder(symbol.Underlying, -(shares_to_buy))
                    self.entry_price[symbol] = symbol_price
                    self.first_dydx_sell[symbol] = True
                    self.short_entry[symbol] = True
                    self.trade_count[symbol] += 1 
                    self.Log(f"{symbol}: Short at {symbol_price} (MACD < Signal)")
                
                if symbol in self.short_entry and symbol in self.first_dydx_sell:
                    if self.short_entry[symbol] and self.first_dydx_sell[symbol] and (prev_macd_slope < 0) and (current_macd_slope >= 0):
                        self.Liquidate(symbol.Underlying)
                        self.first_dydx_sell[symbol] = False
                        self.short_entry[symbol] = False
                        self.Log(f"{symbol}: Exit short at {symbol_price} (MACD slope crosses zero)")
                    
                    if self.short_entry[symbol] and self.first_dydx_sell[symbol] and (symbol_price > (self.entry_price[symbol] * 1.01)):
                        self.Liquidate(symbol.Underlying)
                        self.first_dydx_sell[symbol] = False
                        self.short_entry[symbol] = False
                        self.Log(f"{symbol}: Exit short at {symbol_price} (Stopped out)")
                
                    # MACD > Signal / Second Derivative
                if (symbol_price < five_min_low) and (current_macd > current_signal) and self.trade_count[symbol] == 0:
                    cash_per_stock = int(self.Portfolio.Cash / 3)
                    shares_to_buy = int(cash_per_stock / self.Securities[symbol.Underlying].Price)
                    self.ticket = self.MarketOrder(symbol.Underlying, -(shares_to_buy))
                    self.entry_price[symbol] = symbol_price
                    self.signal_cross_check[symbol] = True  
                    self.short_entry[symbol] = True
                    self.trade_count[symbol] += 1  
                    self.Log(f"{symbol}: Short at {symbol_price} (MACD > Signal)")
                
                if symbol in self.short_entry and symbol in self.signal_cross_check and symbol in self.second_dydx_sell:
                    if self.short_entry[symbol] and self.signal_cross_check[symbol] and (current_macd < current_signal):
                        self.second_dydx_sell[symbol] = True
                    if self.short_entry[symbol] and self.second_dydx_sell[symbol] and (prev_macd_slope < current_macd_slope):
                        self.Liquidate(symbol.Underlying)
                        self.signal_cross_check[symbol] = False
                        self.second_dydx_sell[symbol] = False
                        self.short_entry[symbol] = False
                        self.Log(f"{symbol}: Exit short at {symbol_price} (MACD inflection point)")
                    
                    if self.short_entry[symbol] and self.signal_cross_check[symbol] and (symbol_price > (self.entry_price[symbol] * 1.01)):
                        self.Liquidate(symbol.Underlying)
                        self.signal_cross_check[symbol] = False
                        self.second_dydx_sell[symbol] = False
                        self.short_entry[symbol] = False
                        self.Log(f"{symbol}: Exit short at {symbol_price} (Stopped out)")

                # Liquidate at the end of the day
                if self.liquidate and self.Portfolio[symbol.Underlying].Invested:
                    self.Liquidate(symbol.Underlying)
                    self.liquidate = False
                    self.Log(f'{symbol} Liquidate at the end of the day {symbol_price}')

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            if security.Symbol not in self.macdBySymbol:
                estimize_release_symbol = self.AddData(EstimizeRelease, security.Symbol).Symbol
                history = self.History([estimize_release_symbol], 10, Resolution.Daily)

                sym = self.AddEquity(security.Symbol, Resolution.Minute)
                symbol_data = SymbolData(self, sym.Symbol, 12, 26, 9, MovingAverageType.Exponential, Resolution.Minute)
                self.macdBySymbol[sym.Symbol] = symbol_data

class SymbolData:
    def __init__(self, algorithm, symbol, fastPeriod, slowPeriod, signalPeriod, movingAverageType, resolution):
        self.symbol = symbol
        self.algorithm = algorithm
        self.macd = MovingAverageConvergenceDivergence(fastPeriod, slowPeriod, signalPeriod, movingAverageType)
        self.warmed_up = False

        self.prev_macd = 0
        self.current_macd = 0

        self.prev_macd_slope = 0
        self.current_macd_slope = 0

        self.current_signal = 0

        # Create a 5-minute consolidator
        self.consolidator = TradeBarConsolidator(timedelta(minutes=5))
 
        # Register the consolidator with the algorithm
        algorithm.SubscriptionManager.AddConsolidator(symbol, self.consolidator)

        # Update the MACD indicator with the 5-minute bars
        self.consolidator.DataConsolidated += self.OnFiveMinuteBar

        history = algorithm.History(symbol, 1000, Resolution.Minute).loc[symbol]
        for idx, bar in history.iterrows():
            tradeBar = TradeBar(idx, symbol, bar.open, bar.high, bar.low, bar.close, bar.volume)
            self.consolidator.Update(tradeBar)

    def OnFiveMinuteBar(self, sender, bar):
        self.macd.Update(IndicatorDataPoint(bar.Time, bar.Close))
        if self.macd.IsReady:
            self.prev_macd = self.current_macd
            self.current_macd = self.macd.Current.Value

            self.prev_macd_slope = self.current_macd_slope
            self.current_macd_slope = self.current_macd - self.prev_macd

            self.current_signal = self.macd.Signal.Current.Value

            self.warmed_up = True

