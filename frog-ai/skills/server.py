# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 16:21
import json
import requests

url = "http://192.168.1.101:8000/nlu/parse"

def get_intent(sessionId,content):
    payload = {
        "sessionId": sessionId,
        "text": content
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "PostmanRuntime-ApipostRuntime/1.1.0",
        "Connection": "keep-alive",
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    return json.loads(response.text)

if __name__ == '__main__':
    sessionId = "123"
    content = "微信通知老板晚上聚餐"
    res = get_intent(sessionId,content)
    print(res)

