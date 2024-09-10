from AlgorithmImports import *
from QuantConnect.DataSource import *
from QuantConnect.Data.Market import TradeBar, QuoteBar
from QuantConnect.DataSource import EstimizeConsensus, EstimizeEstimate, EstimizeRelease
from QuantConnect.Data.Consolidators import TradeBarConsolidator
from datetime import datetime, timedelta
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Orders import OrderStatus

def friday_before(earnings_date):
    days_until_friday = (earnings_date.weekday() + 3) % 7
    friday_before_earnings = earnings_date - timedelta(days=days_until_friday)
    
    return friday_before_earnings

def friday_after(earnings_date):
    days_until_friday = (4 - earnings_date.weekday()) % 7
    friday_after_earnings = earnings_date + timedelta(days=days_until_friday)
    
    return friday_after_earnings

class BasicTemplateOptionsAlgorithm(QCAlgorithm):

    def Initialize(self):         

        # INITIALIZE
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2020, 4, 25)
        self.SetCash(100000)

        # EQUITY
        self.equity = self.AddEquity("AAPL", Resolution.Hour)
        self.equity.SetDataNormalizationMode(DataNormalizationMode.SplitAdjusted)

        # OPTION
        option = self.AddOption("AAPL", Resolution.Hour)
        self.option_symbol = option.Symbol
        option.SetFilter(universeFunc=lambda universe: universe.IncludeWeeklys().Strikes(-50, 50).Expiration(timedelta(0), timedelta(50)))
        self.SetBenchmark("AAPL")

        # SCHEDULED EVENT 
        # self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA"), Action(self.OnMarketOpen))

        # VARIABLES

        # AAPL Earning Dates
        self.earnings_report_dates = [datetime(2020, 1, 28), datetime(2020, 4, 30), datetime(2020, 7, 30),
                                datetime(2020, 10, 29), datetime(2021, 1, 27), datetime(2021, 4, 28), datetime(2021, 7, 27), 
                                datetime(2021, 10, 28), datetime(2022, 1, 27), datetime(2022, 4, 28), 
                                datetime(2022, 7, 28), datetime(2022, 10, 27), datetime(2023, 2, 2), 
                                datetime(2023, 5, 4), datetime(2023, 8, 3), datetime(2023, 11, 2)] # Add your dates here 
        
        # # TSLA Earning Dates
        # self.earnings_report_dates = [datetime(2020, 1, 29), datetime(2020, 4, 29), datetime(2020, 7, 22), datetime(2020, 10, 21),
        #                         datetime(2021, 1, 27), datetime(2021, 4, 26), datetime(2021, 7, 26), datetime(2021, 10, 20),
        #                         datetime(2022, 1, 26), datetime(2022, 4, 20), datetime(2022, 7, 20), datetime(2022, 10, 19),
        #                         datetime(2023, 1, 25), datetime(2023, 4, 19), datetime(2023, 7, 19), datetime(2023, 10, 18),
        #                         datetime(2024, 1, 24)]

        self.buy_call_option_strike = 0
        self.buy_put_option_strike = 0
        self.sell_call_option_strike = 0
        self.sell_put_option_strike = 0

        self.entry_buycall_price = 0
        self.entry_buyput_price = 0
        self.entry_sellcall_price = 0
        self.entry_sellput_price = 0

        self.exit_buycall_price = 0 
        self.exit_buyput_price = 0 
        self.exit_sellcall_price = 0 
        self.exit_sellput_price = 0 

        self.net_profit = 0 
        self.cum_profit = 0 
     
        # TOGGLES  
        self.entered = False
    
    def OnData(self, slice):

        self.earnings_report_dates = [date for date in self.earnings_report_dates if date > self.Time]

        for earnings_report_dates in self.earnings_report_dates:
            three_weeks_before_earnings = earnings_report_dates - timedelta(weeks=3)

            # Check if the current date is three weeks before any earnings report dates
            if self.Time.date() == three_weeks_before_earnings.date():# and not self.buy_call and not self.buy_put and not self.sell_call and not self.sell_put:
                # self.Log('Bought contracts')

                # Get the option chain for the specified symbol
                chain = slice.OptionChains.get(self.option_symbol)
                self.Log(f'option chain {chain}')
                if chain and not self.entered:
                    
                    # BUY CALL #
                    # Filter and select BUY call options
                    buy_call_contracts = [contract for contract in chain if contract.Right == OptionRight.Call] 

                    # Sort call options to find the ATM contract with an expiration the friday after earnings_report_dates
                    buy_call_options = sorted(
                        buy_call_contracts,
                        key=lambda x: (
                            abs((chain.Underlying.Price + 10) - x.Strike),
                            0 if x.Expiry == friday_after(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_after(earnings_report_dates))
                        ),
                    )
                    buy_call_option = buy_call_options[0]
                    self.buy_call_option_strike = buy_call_option.Strike
                    
                    # If a put option ATM with correct expiry date is found, trade it
                    if len(buy_call_options) > 0 and buy_call_options[0].Expiry == friday_after(earnings_report_dates):
                        # Get the symbol of the selected call option
                        symbol = buy_call_options[0].Symbol
                        expiry_date = buy_call_options[0].Expiry 
                        self.entry_buycall_price = buy_call_options[0].LastPrice
                        self.Log(f'Buy CALL - Object: {buy_call_option} - Contract Price: {self.entry_buycall_price}')
                        # self.buy_call = True
                    
                    # BUY PUT #
                    # Filter and select BUY call options
                    buy_put_contracts = [contract for contract in chain if contract.Right == OptionRight.Put]

                    # Sort put options to find the ATM contract with an expiration the friday after earnings_report_dates
                    buy_put_options = sorted(
                        buy_put_contracts,
                        key=lambda x: (
                            abs((chain.Underlying.Price - 10) - x.Strike),
                            0 if x.Expiry == friday_after(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_after(earnings_report_dates))
                        ),
                    )
                    buy_put_option = buy_put_options[0]
                    self.buy_put_option_strike = buy_put_option.Strike
                    
                    # If a put option ATM with correct expiry date is found, trade it
                    if len(buy_put_options) > 0 and buy_put_options[0].Expiry == friday_after(earnings_report_dates):
                        # Get the symbol of the selected put option
                        symbol = buy_put_options[0].Symbol
                        expiry_date = buy_put_options[0].Expiry 
                        self.entry_buyput_price = buy_put_options[0].LastPrice
                        self.Log(f'Buy PUT - Object: {buy_put_option} - Contract Price: {self.entry_buyput_price}')
                        # self.buy_put = True

                    # sell CALL #
                    # Filter and select sell call options
                    sell_call_contracts = [contract for contract in chain if contract.Right == OptionRight.Call]

                    # Sort call options to find the ATM contract with an expiration the friday before earnings_report_dates
                    sell_call_options = sorted(
                        sell_call_contracts,
                        key=lambda x: (
                            abs((chain.Underlying.Price + 10) - x.Strike),
                            0 if x.Expiry == friday_before(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_before(earnings_report_dates))
                        ),
                    )
                    sell_call_option = sell_call_options[0]
                    self.sell_call_option_strike = sell_call_option.Strike
                    
                    # If a put option ATM with correct expiry date is found, trade it
                    if len(sell_call_options) > 0 and sell_call_options[0].Expiry == friday_before(earnings_report_dates):
                        # Get the symbol of the selected call option
                        symbol = sell_call_options[0].Symbol
                        expiry_date = sell_call_options[0].Expiry 
                        self.entry_sellcall_price = sell_call_options[0].LastPrice
                        self.Log(f'Sell CALL - Object: {sell_call_option} - Contract Price: {self.entry_sellcall_price}')
                        # self.sell_call = True
                    
                    # sell PUT #
                    # Filter and select sell call options
                    sell_put_contracts = [contract for contract in chain if contract.Right == OptionRight.Put]

                    # Sort put options to find the ATM contract with an expiration the friday before earnings_report_dates
                    sell_put_options = sorted(
                        sell_put_contracts,
                        key=lambda x: (
                            abs((chain.Underlying.Price - 10) - x.Strike),
                            0 if x.Expiry == friday_before(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_before(earnings_report_dates))
                        ),
                    )
                    sell_put_option = sell_put_options[0]
                    self.sell_put_option_strike = sell_put_option.Strike
                    
                    # If a put option ATM with correct expiry date is found, trade it
                    if len(sell_put_options) > 0 and sell_put_options[0].Expiry == friday_before(earnings_report_dates):
                        # Get the symbol of the selected put option
                        symbol = sell_put_options[0].Symbol
                        expiry_date = sell_put_options[0].Expiry 
                        self.entry_sellput_price = sell_put_options[0].LastPrice
                        self.Log(f'Sell PUT - Object: {sell_put_option} - Contract Price: {self.entry_sellput_price}')
                        # self.sell_put = True
                    
                self.entered = True

            # EXIT    
            if self.Time.date() == (friday_before(earnings_report_dates)).date() and self.entered:
                
                # Get the option chain for the specified symbol
                chain = slice.OptionChains.get(self.option_symbol)
                self.Log(f'option chain {chain}')
                if chain:
                    self.Log('gets to here')
                    # BUY CALL #
                    # Filter and select BUY call options
                    buy_call_contracts = [contract for contract in chain if contract.Right == OptionRight.Call]

                    # Sort call options to find the ATM contract with an expiration the friday after earnings_report_dates
                    buy_call_options = sorted(
                        buy_call_contracts,
                        key=lambda x: (
                            abs(self.buy_call_option_strike - x.Strike),
                            0 if x.Expiry == friday_after(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_after(earnings_report_dates))
                        ),
                    )
                    
                    buy_call_option = buy_call_options[0]
                    if len(buy_call_options) > 0 and buy_call_options[0].Expiry == friday_after(earnings_report_dates):
                        # Get the symbol of the selected call option
                        symbol = buy_call_options[0].Symbol
                        expiry_date = buy_call_options[0].Expiry 
                        self.exit_buycall_price = buy_call_options[0].LastPrice
                        self.Log(f'Buy CALL - Object: {buy_call_option} - Exit Contract Price: {self.exit_buycall_price}') 
                        # self.buy_call = False 

                    # BUY put #
                    # Filter and select BUY put options
                    buy_put_contracts = [contract for contract in chain if contract.Right == OptionRight.Put]

                    # Sort put options to find the ATM contract with an expiration the friday after earnings_report_dates
                    buy_put_options = sorted(
                        buy_put_contracts,
                        key=lambda x: (
                            abs(self.buy_put_option_strike - x.Strike),
                            0 if x.Expiry == friday_after(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_after(earnings_report_dates))
                        ),
                    )
                    
                    buy_put_option = buy_put_options[0]
                    if len(buy_put_options) > 0 and buy_put_options[0].Expiry == friday_after(earnings_report_dates):
                        # Get the symbol of the selected put option
                        symbol = buy_put_options[0].Symbol
                        expiry_date = buy_put_options[0].Expiry 
                        self.exit_buyput_price = buy_put_options[0].LastPrice
                        self.Log(f'Buy PUT - Object: {buy_put_option} - Exit Contract Price: {self.exit_buyput_price}')  
                        # self.buy_put = False 


                    # sell CALL #
                    # Filter and select sell call options
                    sell_call_contracts = [contract for contract in chain if contract.Right == OptionRight.Call]

                    # Sort call options to find the ATM contract with an expiration the friday before earnings_report_dates
                    sell_call_options = sorted(
                        sell_call_contracts,
                        key=lambda x: (
                            abs(self.sell_call_option_strike - x.Strike),
                            0 if x.Expiry == friday_before(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_before(earnings_report_dates))
                        ),
                    )
                    
                    sell_call_option = sell_call_options[0]
                    if len(sell_call_options) > 0 and sell_call_options[0].Expiry == friday_before(earnings_report_dates):
                        # Get the symbol of the selected call option
                        symbol = sell_call_options[0].Symbol
                        expiry_date = sell_call_options[0].Expiry 
                        self.exit_sellcall_price = sell_call_options[0].LastPrice
                        self.Log(f'Sell CALL - Object: {sell_call_option} - Exit Contract Price: {self.exit_sellcall_price}')
                        # self.sell_call = False 

                    # sell put #
                    # Filter and select sell put options
                    sell_put_contracts = [contract for contract in chain if contract.Right == OptionRight.Put]

                    # Sort put options to find the ATM contract with an expiration the friday before earnings_report_dates
                    sell_put_options = sorted(
                        sell_put_contracts,
                        key=lambda x: (
                            abs(self.sell_put_option_strike - x.Strike),
                            0 if x.Expiry == friday_before(earnings_report_dates) else 1,  
                            abs(x.Expiry - friday_before(earnings_report_dates))
                        ),
                    )
                    
                    sell_put_option = sell_put_options[0]
                    if len(sell_put_options) > 0 and sell_put_options[0].Expiry == friday_before(earnings_report_dates):
                        # Get the symbol of the selected put option
                        symbol = sell_put_options[0].Symbol
                        expiry_date = sell_put_options[0].Expiry 
                        self.exit_sellput_price = sell_put_options[0].LastPrice
                        self.Log(f'Sell PUT - Object: {sell_put_option} - Exit Contract Price: {self.exit_sellput_price}')
                        # self.sell_put = False 

                    self.net_profit = (self.exit_buycall_price - self.entry_buycall_price) + (self.exit_buyput_price - self.entry_buyput_price) + (self.entry_sellcall_price - self.exit_sellcall_price) + (self.entry_sellput_price - self.exit_sellput_price)
                    self.cum_profit = self.cum_profit + self.net_profit
                    self.Log(f'Net Profit: {self.net_profit} | Cumulative Profit: {self.cum_profit}')
                self.entered = False  


        
