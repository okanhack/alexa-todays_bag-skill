# -*- coding: utf-8 -*-
#
# Copyright 2020 Okanhack. All Rights Reserved.
#
from datetime import datetime
import requests
from collections import OrderedDict

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# livedoor WeatherHacksAPI
WEATHER_API = "http://weather.livedoor.com/forecast/webservice/json/v1?city={}"

def get_daily_items(dt:datetime, attr:dict):
    """ 永続アトリビュートから、日付によりアイテムを取得する.
    
    Args:
        dt (datetime) : 取得するキー.
        attr (dict) : 永続アトリビュート.
        
    Returns:
        list[str]:アイテムの配列.平日/土日 > 曜日 > 指定日 の順に重複なしでソート.
    """
    ret = []
    ret_day = []
    ret_weekday = []
    ret_day_group = []
    
    # 曜日を取得
    weekday = dt.weekday()
    
    # アトリビュートを検索
    for key in attr:
        if key == dt.strftime("%Y-%m-%d"):
            # 特定日
            ret_day = attr[key].split(",")
        
        elif key == str(weekday):
            # 特定曜日
            ret_weekday = attr[key].split(",")
        
        elif (key == "7" and weekday < 5) or (key == "8" and weekday >= 5):
            # 平日、土日
            ret_day_group = attr[key].split(",")
            
    # 重複を削除した配列を返す
    ret = list(OrderedDict.fromkeys(ret_day_group + ret_weekday + ret_day))
    return ret

def get_items_by_key(key:str, attr:dict):
    """ 永続アトリビュートから、キーによりアイテムを取得する.
    
    対象となるキーは0~8(曜日、平日、休日)または、 %Y-%m-%d形式の日付文字列.
    
    Args:
        key (str) : 取得するキー.
        attr (dict) : 永続アトリビュート.
        
    Returns:
        list[str]:アイテムの配列.
    """
    # 曜日を番号に変換
    ret = []
    if key == None:
        return ret
    
    # アトリビュートを検索
    if not key in attr:
        return ret
    
    # 値を取得
    values = attr[key].split(",")
    ret = values
            
    # 配列を返す
    return ret

def get_items_by_wether(dt:datetime, city_code:str, lang:dict):
    """ 天気による持ち物を取得する。
    
    Wether Hack APIから天気を取得し、天候に応じたメッセージを返す.
    Wether Hack APIの仕様は http://weather.livedoor.com/weather_hacks/webservice を参照のこと.
    
    Args:
        dt (datetime) : 日付.
        city_code (str) : 都市コード.
        
    Returns:
        str: メッセージの文字列.
    """
    
    ret = ""
    forecast = None
    telop = ""
    max_temp = -999
    min_temp = 999
    
    # JSON形式で取得
    uri = WEATHER_API.format(city_code)
    weather = requests.get(uri).json()
    
    # 予報を検索
    for f in weather["forecasts"]:

        if f["date"] == dt.strftime("%Y-%m-%d"):
            
            forecast = f
                
            break
    
    # Debub
    logger.info(forecast)
    
    # 該当する日がない場合は、何も言わない。
    if forecast is None:
        return ""
    
    # 概況、最高気温、最低気温を取得
    telop = forecast['telop']
    if forecast['temperature']['max'] is not None:
        max_temp = int(forecast['temperature']['max']['celsius'])
    if forecast['temperature']['min'] is not None:
        min_temp = int(forecast['temperature']['min']['celsius'])
    
    # 概況
    ret += lang['WETHER_ITEM'].format(telop)
    
    # 天候による持ち物（雨、雪、暴風[雨]など）
    if "雨" in telop or "雪" in telop:
        ret += lang['RAINY_DAY_MSG']
    
    # 気温による持ち物
    if max_temp >= 25:
        ret += lang['HOT_DAY_MSG']
        
    elif max_temp <= 10:
        ret += lang['COLD_DAY_MSG']
        
    elif max_temp - min_temp >= 10:
        ret += lang['HIGH_LOW_DAY_MSG']
    
    return ret

def get_weekday_id(day_of_week:str):
    """ 曜日をキーに変換する.
    
    0:mon 1:tue 2:wed 3:thu 4:fri 5:sat 6:sun 7:weekday 8:weekend.
    
    
    Args:
        day_of_week (str) : 曜日名（"月曜日"など）.
        
    Returns:
        str: キー.
    """
    # 0:mon 1:tue 2:wed 3:thu 4:fri 5:sat 6:sun 7:weekday 8:holiday
    weekday_list = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日", "平日", "土日", "週末"]
    
    ret = None
    
    # 曜日に該当しなければ、終了
    if not day_of_week in weekday_list:
        return ret
    
    # 曜日をキーに変換
    key = weekday_list.index(day_of_week)
    
    # 週末は土日と同じ扱い
    if key > 8:
        key = 8
    
    ret = str(key)
    
    return ret
