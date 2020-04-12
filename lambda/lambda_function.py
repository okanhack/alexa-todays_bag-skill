# -*- coding: utf-8 -*-
#
# Copyright 2020 Okanhack. All Rights Reserved.
#
import logging
import os
import boto3
import json

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
from ask_sdk_s3.adapter import S3Adapter

bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
s3_adapter = S3Adapter(bucket_name=bucket_name, path_prefix="Media", s3_client=s3_client)
sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from datetime import datetime, timedelta, timezone
import locale
import item_function

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import pytz
import re

# 状態-追加
STATE_ADD = "ADD"

# 状態-削除
STATE_CLEAR = "CLEAR"

# 間を開けて話す
BREAK_SPEECH = "<break time='0.5s'/>"

@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    """
    Handler for Skill Launch.
    """
    # type: (HandlerInput) -> Response
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # 永続アトリビュートを取得
    attr = handler_input.attributes_manager.persistent_attributes
    if not attr:
        speech_text = lang['WELCOME_MSG']
        reprompt = lang['ASK_MSG']
        
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
        
    # 明日の日付
    dt = datetime.now(get_timezone(handler_input.request_envelope.context.system))
    current = lang['TODAY']
    
    # 午前9時代より前は、日付を変えないこととする。
    if dt.hour > 9 :
        dt = dt + timedelta(days=1)
        current = lang['TOMORROW']
    
    # 日付依存の持ち物
    daily_item_list = item_function.get_daily_items(dt, attr)
    if len(daily_item_list) == 0:
        dailyitems = lang['NO_ITEM']
    else:
        dailyitems = lang['ITEM_LIST'].format((", " + BREAK_SPEECH).join(daily_item_list))
    
    weather_items = ""
    # city_codeが登録されていれば天気による持ち物を追加
    if "city_code" in attr:
        # 天気による持ち物
        weather_items = item_function.get_items_by_wether(dt, attr['city_code'], lang)
        
    # 応答メッセージ
    speech_text = lang['DAILY_MSG'].format(current, dt.strftime(lang['DATE_FORMAT']), dailyitems, weather_items)
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

#### 検索系 #####

@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("ItemListIntent")(input))
def item_list_intent_handler(handler_input):
    """
    Handler for ItemList.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    # 対象の日付を取得
    slot_value = handler_input.request_envelope.request.intent.slots['target_date'].value
    logger.info("slot_value is "+ slot_value)
    
    dt = None
    try:
        # 日付に変換
        dt = datetime.strptime(slot_value, "%Y-%m-%d")
    except:
        # 応答メッセージ
        speech_text = "その日付には対応していません。年月日で指定してください。"
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        
    # 永続アトリビュートから登録されているアイテムを取得
    p_attrs = handler_input.attributes_manager.persistent_attributes
    
    # 日付依存の持ち物
    daily_item_list = item_function.get_daily_items(dt, p_attrs)
    if len(daily_item_list) == 0:
        dailyitems = lang['NO_ITEM']
    else:
        dailyitems = lang['ITEM_LIST'].format((", " + BREAK_SPEECH).join(daily_item_list))
        
    weather_items = ""
    if "city_code" in p_attrs:
        # 天気による持ち物
        weather_items = item_function.get_items_by_wether(dt, p_attrs['city_code'], lang)
    
    # 応答メッセージ
    speech_text = lang['ITEM_LIST_MSG'].format(dt.strftime(lang['DATE_FORMAT']), dailyitems, weather_items)
    reprompt = lang['ASK_MSG']

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("CheckItemIntent")(input))
def check_item_intent_handler(handler_input):
    """
    Handler for CheckItemIntent.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes['_']
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    # スロットから値を取得
    slot_value = handler_input.request_envelope.request.intent.slots['day_of_week'].value
    logger.info("slot_value is "+ slot_value)
    
    # 曜日IDに変換
    day_of_week = item_function.get_weekday_id(slot_value)
    
    # 永続アトリビュートを取得
    p_attrs = handler_input.attributes_manager.persistent_attributes
    
    # 曜日に登録されているものを取得
    daily_item_list = item_function.get_items_by_key(day_of_week, p_attrs)
    
    if len(daily_item_list) == 0:
        dailyitems = lang['NO_ITEM']
    else:
        dailyitems = lang['ITEM_LIST'].format((", " + BREAK_SPEECH).join(daily_item_list))
    
    # 応答メッセージ
    speech_text = lang['CHECK_ITEM_MSG'].format(slot_value, dailyitems)
    reprompt = lang['ASK_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

#### 登録系 #####
@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("AddIntent")(input))
def add_intent_handler(handler_input):
    """
    Handler for AddIntent.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # スロットから対象の品目を取得
    slot_item = handler_input.request_envelope.request.intent.slots["item"].value
    logger.info(slot_item)
    
    # セッションアトリビュートを「登録中」に
    s_attrs = {}
    s_attrs['state'] = STATE_ADD
    s_attrs['date'] = ""
    s_attrs['date_speak'] = ""
    s_attrs['item'] = slot_item
    handler_input.attributes_manager.session_attributes = s_attrs
    
    speech_text  = lang['ADD_CONFIRM_MSG'].format(slot_item) + lang['ADD_DATE_MSG']
    reprompt = lang['ADD_DATE_MSG'] + lang['DATE_REPROMPT_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input:
                    get_state(input) == STATE_ADD and
                    is_intent_name("SetDateIntent")(input))
def set_date_intent_handler(handler_input):
    """
    Handler for SetDateIntent when add a item.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # 対象の日付を取得
    slot_date1 = handler_input.request_envelope.request.intent.slots['target_date'].value
    slot_date2 = handler_input.request_envelope.request.intent.slots['day_of_week'].value
    logger.info(slot_date1)
    logger.info(slot_date2)
    
    date_key = get_key(slot_date1, slot_date2, lang['DATE_FORMAT'])
    date = date_key['key']
    date_speak = date_key['speech_text']
    
    # 日付が設定できない場合は、再度促す
    if date == None or date_speak == "":
        speech_text = lang['ADD_DATE_MSG']
        reprompt = lang['ADD_DATE_MSG'] + lang['DATE_REPROMPT_MSG']
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
    
    # セッションアトリビュートから対象の品目を指定
    s_attrs = handler_input.attributes_manager.session_attributes
    item = s_attrs['item']
    
    # 永続アトリビュートから登録されているアイテムを取得
    p_attrs = handler_input.attributes_manager.persistent_attributes
    daily_item_list = item_function.get_items_by_key(date, p_attrs)
    
    # 重複登録をチェック
    if item in daily_item_list:
        # セッションアトリビュートをクリアして終了
        handler_input.attributes_manager.session_attributes.clear()
        
        speech_text  = lang['DUPLICATE_ITEM_MSG']
        reprompt = lang['ASK_MSG']
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
        
    # 追加して登録
    daily_item_list.append(item)
    p_attrs[date] = ",".join(daily_item_list) 
    handler_input.attributes_manager.persistent_attributes = p_attrs
    handler_input.attributes_manager.save_persistent_attributes()
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    # 応答データ作成
    dailyitems = lang['ITEM_LIST'].format((","+ BREAK_SPEECH).join(daily_item_list))
    
    speech_text  = lang['ADD_COMPLETE_MSG'].format(item, date_speak)
    speech_text += lang['CHECK_ITEM_MSG'].format(date_speak, dailyitems)
    reprompt = lang['ASK_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

#### 削除系（要素全消し） #####
@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("ClearIntent")(input) or
                    (get_state(input) == STATE_CLEAR and
                    is_intent_name("SetDateIntent")(input)))
def clear_intent_handler(handler_input):
    """
    Handler for ClearIntent.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # 対象の日付を取得
    slot_date1 = handler_input.request_envelope.request.intent.slots['target_date'].value
    slot_date2 = handler_input.request_envelope.request.intent.slots['day_of_week'].value
    logger.info(slot_date1)
    logger.info(slot_date2)
    
    date_key = get_key(slot_date1, slot_date2, lang['DATE_FORMAT'])
    date = date_key['key']
    date_speak = date_key['speech_text']
    
    # 日付が設定できない場合は、再度促す
    if date == None or date_speak == "":
        # 削除中を認識
        s_attrs = {}
        s_attrs['state'] = STATE_CLEAR
        handler_input.attributes_manager.session_attributes = s_attrs
        speech_text = lang['DEL_DATE_MSG']
        reprompt = speech_text + lang['DATE_REPROMPT_MSG']
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
    
    # 永続アトリビュートから登録されているアイテムを取得
    p_attrs = handler_input.attributes_manager.persistent_attributes
    daily_item_list = item_function.get_items_by_key(date, p_attrs)
    
    # 0件の場合は中止
    if len(daily_item_list) == 0:
        handler_input.attributes_manager.session_attributes.clear()
        speech_text  = lang['DEL_NO_ITEM_MSG'].format(date_speak)
        reprompt = lang['ASK_MSG']
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response
        
    # セッションアトリビュートを「削除中」に
    s_attrs = {}
    s_attrs['state'] = STATE_CLEAR
    s_attrs['date'] = date
    s_attrs['date_speak'] = date_speak
    s_attrs['item'] = ""
    handler_input.attributes_manager.session_attributes = s_attrs
    
    # 応答メッセージ
    dailyitems = lang['ITEM_LIST'].format(("," + BREAK_SPEECH).join(daily_item_list))
    
    # 応答データ作成
    speech_text += lang['ITEM_LIST_MSG'].format(date_speak, dailyitems, "")
    speech_text += lang['DEL_CONFIRM_MSG']
    reprompt = speech_text + lang['DEL_REPROMPT_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input:
                    get_state(input) == STATE_CLEAR and
                    is_intent_name("AMAZON.YesIntent")(input))
def clear_item_intent_handler(handler_input):
    """
    Handler for YesIntent when clear item.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # セッションアトリビュートから対象の品目,日時を指定
    s_attrs = handler_input.attributes_manager.session_attributes
    date = s_attrs['date']
    date_speak = s_attrs['date_speak']
    
    # 永続アトリビュートを取得
    p_attrs = handler_input.attributes_manager.persistent_attributes
    
    # 永続アトリビュートの該当項目を削除
    del p_attrs[date]
    handler_input.attributes_manager.persistent_attributes = p_attrs
    handler_input.attributes_manager.save_persistent_attributes()
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    speech_text  = lang['DEL_COMPLETE_MSG'].format(date_speak)
    reprompt = lang['ASK_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

#### 登録・削除共通 #####
@sb.request_handler(can_handle_func=lambda input:
        (get_state(input) == STATE_ADD or 
        get_state(input) == STATE_CLEAR) and
        (is_intent_name("AMAZON.NoIntent")(input) or
        is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input)))
def cancel_intent_handler(handler_input):
    """
    Handler for NoIntent when add or clear.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    speech_text = lang['CANCEL_MSG']
    reprompt = lang['ASK_MSG']
    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response


#### 地域設定 #####
@sb.request_handler(can_handle_func=lambda input:
                    is_intent_name("GetAreaIntent")(input))
def get_area_intent_handler(handler_input):
    """
    Handler for GetAreaIntent.
    """
    speech_text = ""
    reprompt = ""
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    # セッションアトリビュートをクリア
    handler_input.attributes_manager.session_attributes.clear()
    
    # 地域を取得
    pref = handler_input.request_envelope.request.intent.slots['pref'].value
    city = handler_input.request_envelope.request.intent.slots['city'].value
    
    AREA_XML = "http://weather.livedoor.com/forecast/rss/primary_area.xml"
    req = urllib.request.Request(AREA_XML)
     
    with urllib.request.urlopen(req) as response:
        xml_string = response.read()
        
    root = ET.fromstring(xml_string)
    
    city_list = []
    
    # city_codeを検索
    for pref_node in root.iter('pref'):
        logger.info(pref_node.attrib['title'])
        
        if pref == pref_node.attrib['title'] or (pref == "北海道" and "道" in pref_node.attrib['title']):
            # 都道府県に一致
            for city_node in pref_node.iter('city'):
                city_list.append(city_node.attrib['title'])
                
                if re.match(city_node.attrib['title'] + "(|市)", city):
                    # 永続アトリビュートを編集
                    p_attrs = handler_input.attributes_manager.persistent_attributes
                    p_attrs['city_code'] = city_node.attrib['id']
                    handler_input.attributes_manager.persistent_attributes = p_attrs
                    handler_input.attributes_manager.save_persistent_attributes()
                    
                    speech_text = lang['CHANGE_AREA_COMPLETE_MSG'].format(pref, city)
                    reprompt = lang['ASK_MSG']
                    handler_input.response_builder.speak(speech_text).ask(reprompt)
                    return handler_input.response_builder.response
    
    # 取得できな買った場合はエラーメッセージ
    speech_text = lang['FAIL_CHANGE_AREA_MSG'].format(pref, ",".join(city_list))
    handler_input.response_builder.speak(speech_text).ask(speech_text)
    return handler_input.response_builder.response

###########

def get_state(handler_input):
    """ セッションアトリビュートから状態を表す文字列を取得する.
    
    Args:
        handler_input (object) : handler_input.
        
    Returns:
        str : 状態を表す文字列.
    """
    # type: (HandlerInput) -> str
    state = ""
    s_attrs = handler_input.attributes_manager.session_attributes

    if "state" not in s_attrs :
        return state
        
    elif s_attrs['state'] == STATE_ADD or s_attrs['state'] == STATE_CLEAR:
        return s_attrs['state']
        
    return state

def get_key(target_date, day_of_week, date_format:str):
    """ 日付指定または曜日指定でスロットを渡された時に、登録するキーと読み上げ用の日付を返す.
    
    Args:
        target_date (str) : 日付文字列（AMAZON.DATEスロット）.
        day_of_week (str) : 曜日の文字列（AMAZON.DAY_OF_WEEKスロット）.
        
    Returns:
        dict : 解析結果. key:永続アトリビュートに登録する時のキー, speech_text:Alexaが読み上げる時の文字列, date : 日付(datetime型, 日付指定時のみ)
    """
    
    ret = {"key":None, "speech_text":"", "date":None}
    
    if target_date != None :
        try:
            # 例外処理で有効な日付か判定（DATEスロットは、年のみの指定も受け付ける。）
            dt = datetime.strptime(target_date, '%Y-%m-%d')
            ret["key"] = target_date
            ret["speech_text"] = dt.strftime(date_format)
            ret["date"] = dt
            
        except ValueError:
            ret["key"] = None
            
    elif day_of_week != None :
        ret["key"] = item_function.get_weekday_id(day_of_week)
        ret["speech_text"] = day_of_week
    
    return ret

def get_timezone(sys_object):
    """ システムオブジェクトからタイムゾーンを取得する.
    
    シミュレーターで行う場合、タイムゾーンが取得できないので、デフォルトは'Asia/Tokyo'にしている.
    
    Args:
        sys_object (object) : システムオブジェクト.
        
    Returns:
        pytz.timezone : ユーザーのタイムゾーン.
    """
    # get device id
    device_id = sys_object.device.device_id

    # get systems api information
    api_endpoint = sys_object.api_endpoint
    api_access_token = sys_object.api_access_token
    
    # construct systems api timezone url
    url = '{api_endpoint}/v2/devices/{device_id}/settings/System.timeZone'.format(api_endpoint=api_endpoint, device_id=device_id)
    headers = {'Authorization': 'Bearer ' + api_access_token}

    userTimeZone = ""
    try:
        r = requests.get(url, headers=headers)
        res = r.json()
        logger.info("Device API result: {}".format(str(res)))
        userTimeZone = str(res)
    except Exception:
        #TODO:実機用
        #handler_input.response_builder.speak("There was a problem connecting to the service")
        #return handler_input.response_builder.response
        
        # Default TimeZone = Tokyo(実機でしかセットできないため)
        userTimeZone = 'Asia/Tokyo'
    
    return pytz.timezone(userTimeZone)


#================
@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    """Handler for Help Intent."""
    # type: (HandlerInput) -> Response
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    
    speech_text  = lang['HELP_MSG']
    reprompt = lang['ASK_MSG']

    handler_input.response_builder.speak(speech_text).ask(reprompt)
    return handler_input.response_builder.response

@sb.request_handler(
    can_handle_func=lambda input:
        get_state(input) == "" and
        (is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input)))
def cancel_and_stop_intent_handler(handler_input):
    """Single handler for Cancel and Stop Intent."""
    # type: (HandlerInput) -> Response
    
    # 多言語応答データを取得
    lang = handler_input.attributes_manager.request_attributes["_"]
    speech_text = lang['GOODBYE_MSG']

    handler_input.response_builder.speak(
        speech_text).set_should_end_session(True)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    """Handler for Session End."""
    # type: (HandlerInput) -> Response
    logger.info(
        "Session ended with reason: {}".format(
            handler_input.request_envelope.request.reason))
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input: True)
def unhandled_intent_handler(handler_input):
    """Handler for all other unhandled requests."""
    # type: (HandlerInput) -> Response
    lang = handler_input.attributes_manager.request_attributes["_"]
    speech = lang['UNHANDLED_MSG']
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    # type: (HandlerInput, Exception) -> Response
    logger.error(exception, exc_info=True)
    lang = handler_input.attributes_manager.request_attributes["_"]
    speech = lang['ERROR_MSG']
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


@sb.global_request_interceptor()
def localization_intercepter(handler_input):
    """
    Add function to request attributes, that can load locale specific data.
    """
    skill_locale = handler_input.request_envelope.request.locale

    # language_strings.jsonから言語用データを取得
    with open("language_strings.json") as language_prompts:
        language_data = json.load(language_prompts)
    # set default translation data to broader translation
    data = language_data[skill_locale[:2]]
    
    # if a more specialized translation exists, then select it instead
    # example: "fr-CA" will pick "fr" translations first, but if "fr-CA" translation exists,
    #          then pick that instead
    if skill_locale in language_data:
        data.update(language_data[skill_locale])
    handler_input.attributes_manager.request_attributes["_"] = data

    # configure the runtime to treat time according to the skill locale
    skill_locale = skill_locale.replace('-','_')
    
    locale.setlocale(locale.LC_TIME, skill_locale)

lambda_handler = sb.lambda_handler()
