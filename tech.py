import ffn
from flask import Flask
import numpy as np
import pandas as pd
import pandas_datareader.data as web
import requests
from datetime import datetime
import pickle
import talib
from talib import MA_Type
import requests
import io
import pickle

# 計算 MaxDD
def DrawDownAnalysis(cumRet):
    dd_series = ffn.core.to_drawdown_series(cumRet)
    dd_details = ffn.core.drawdown_details(dd_series)
    return dd_details['drawdown'].min(), dd_details['days'].max()

def indicators(df):
    dailyRet = df['Close'].pct_change()
    excessRet = (dailyRet - 0.04/252)[df['positions'] == 1]
    SharpeRatio = np.sqrt(252.0)*np.mean(excessRet)/np.std(excessRet)
    
    cumRet = np.cumprod(1+excessRet)
    
    maxdd, maxddd = DrawDownAnalysis(cumRet)
    
    return SharpeRatio, maxdd, maxddd, cumRet[-1]

def KD_way(df):
    df["K"], df["D"] = talib.STOCHF(df["High"].values, df["Low"].values, df['Close'].values,
                                    fastk_period=9, fastd_period=9,fastd_matype=MA_Type.T3)
    #KD20以下黃金交叉向上買進多單，80以上死亡交叉往下買進空單---------從30/70改20/80，績效較佳。
    has_position = False
    df['signals'] = 0
    for t in range(2, df['signals'].size):
        if (df['K'][t] > df["D"][t-1])|(df["D"][t] > 40):
            if not has_position:
                df.loc[df.index[t], 'signals'] = 1
                has_position = True
        elif (df['K'][t] < df["D"][t-1])|(df["D"][t] < 60):
            if has_position:
                df.loc[df.index[t], 'signals'] = -1
                has_position = False

    df['positions'] = df['signals'].cumsum().shift()
    return df

# 計算月均線
# 布林通道
#帶狀上限 = 帶狀中心線 + 1個標準差
#帶狀中心線 = 20MA
#帶狀下限 = 帶狀中心線 - 1個標準差
#BBands_strategy
def BBands_strategy(df):
    df['20d'] = pd.Series.rolling(df['Close'], window=20).mean()
    df['20dstd'] = pd.Series.rolling(df['Close'], window=20).std()
    df['UBB'] = df['20d']+1*df['20dstd']
    df['MBB'] = df['20d']
    df['LBB'] = df['20d']-1*df['20dstd']
    #bb_更改後--
    has_position = False
    df['signals'] = 0
    for t in range(2, df['signals'].size):
        if ( df['Close'][t] > df['LBB'][t] and df['Close'][t-1] < df['LBB'][t-1]) :   #買進訊號:價格下到上突破LBB
            if not has_position:
                df.loc[df.index[t], 'signals'] = 1
                has_position = True
        elif ( df['Close'][t-1] > df['UBB'][t-1] and df['Close'][t] > df['UBB'][t] ):  #賣出訊號:價格上到下突破MBB
            if has_position:
                df.loc[df.index[t], 'signals'] = -1
                has_position = False

    df['positions'] = df['signals'].cumsum().shift()
    return df

def MACD(df):
    df['DIF'] = pd.Series.ewm(df['Close'],span=12,min_periods=1).mean()-pd.Series.ewm(df['Close'],span=26,min_periods=1).mean()
    df['DEA'] = pd.Series.ewm(df['DIF'],span=9,min_periods=1).mean()
    df['MACD'] = (df['DIF']-df['DEA'])*2
    
    has_position = False
    df['signals'] = 0
    
    for t in range(2, df['signals'].size):
            if df['DIF'][t] > df['DEA'][t] and df['DIF'][t-1] < df['DEA'][t-1]: #and df['DIF'][t] < 0 and df['DEA'][t] < 0:
                if not has_position:
                    df.loc[df.index[t], 'signals'] = 1
                    has_position = True
            elif df['DIF'][t] < df['DEA'][t] and df['DIF'][t-1] > df['DEA'][t-1]: #and df['DIF'][t] > 0 and df['DEA'][t] > 0:
                if has_position:
                    df.loc[df.index[t], 'signals'] = -1
                    has_position = False
                    
    df['positions'] = df['signals'].cumsum().shift()
    return df

#單純做日線穿越月線就買入
def Gold_cross(df):
    has_position = False
    df['signals'] = 0
    
    df['MA5'] = talib.MA(df['Close'].values,5,matype=0)
    df['MA20'] = talib.MA(df['Close'].values,15,matype=0)
    
    for t in range(2, df['signals'].size):
        if df['Close'][t] > df['MA5'][t-1] and df['MA5'][t-1] > df['MA20'][t-1] and df['MA5'][t-2] < df['MA20'][t-2]  :
            if not has_position:
                df.loc[df.index[t], 'signals'] = 1
                has_position = True
        elif df['Close'][t] < df['MA5'][t-1] :
            if has_position:
                df.loc[df.index[t], 'signals'] = -1
                has_position = False
    

    df['positions'] = df['signals'].cumsum().shift()
    return df

def apply_strategy(strategy, df):
    return strategy(df)