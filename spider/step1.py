
# 192.168.2.1
from lxml import etree
import re
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
import random
import ast


def input_proxies():
    proxies_list = []
    with open('spider/proxies.txt', 'r', encoding='utf-8') as f:
        line = 'line'
        while line:
            line = f.readline().strip()
            proxies_list.append(line)
    if proxies_list:
        return proxies_list
    else:
        print('fail to get proxies_list')
        return 'fail'


def one_url():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    c = set()
    for i in range(1, 2):  # 此处范围为第几页到第几页
        url = f"https://github.com/search?q=feat+%22test+plan%22+language%3APython+&type=pullrequests&p={i}"
        # proxies_list = input_proxies()
        # num = random.randint(0, len(proxies_list) - 1)
        # proxies = ast.literal_eval(proxies_list[num])
        resp = requests.get(url=url, headers=headers, proxies={"http": None, "https": None})
        resp.encoding = 'utf-8'
        tree = etree.HTML(resp.text)
        nodes1 = tree.xpath(f"/html/body/div[1]//a[@class]/@href")
        pattern = r'^/.+/\w+/\w+/\d+'
        matched_strings = [s for s in nodes1 if re.search(pattern, s)]
        truncated_strings = [re.sub(r'/\d+$', '', s) for s in matched_strings]
        truncated_strings = set(truncated_strings)
        for x in truncated_strings:
            c.add(r'https://github.com/' + x + "s?q=feat+%22test+plan%22+is%3Apr+is%3Amerged+")
    return c

def new_one_url():

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    c = set()
    for i in range(1, 2):  # 此处范围为第几页到第几页
        url = f"https://github.com/search?q=feat+%22test+plan%22+language%3APython+&type=pullrequests&p={i}"
        resp = requests.get(url=url, headers=headers, proxies={"http": None, "https": None})
        resp.encoding = 'utf-8'
        tree = etree.HTML(resp.text)
        
        # 获取包含10个元素的div
        elements = tree.xpath("/html/body/div[1]/div[5]/main/react-app/div/div/div[1]/div/div/div[2]/div[2]/div/div[1]/div[4]/div/div")
        
        for element in elements:
            # 获取每个元素的h3/div[1]/a的url
            urls = element.xpath(".//div/div[1]/h3/div[1]/a/@href")
            for url in urls:
                full_url = f"https://github.com{url}"
                c.add(full_url)
    
    return c
def Page(url):  # 获取页数
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 '
                      'Safari/537.36 Edg/131.0.0.0',
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        resp.encoding = 'utf-8'
        tree = etree.HTML(resp.text)
        a_tag_text = tree.xpath('//a[@class="btn-link selected"]/text()')
        a_tag_text = [x.strip().replace(',', '') for x in set(a_tag_text)]
        result = ''.join([str(i) for i in a_tag_text])
        result = re.sub(r'\D', '', result)
        return int((int(result) / 25))


def new_url():
    c1 = set()
    one_urls = new_one_url()
    for url in one_urls:
        pages = Page(url)
        for i in range(1, pages + 1):
            c1.add(url + f'&page={i}')
    return c1


def need_url(set1, x):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    url = x
    proxies_list = input_proxies()
    num = random.randint(0, len(proxies_list) - 1)
    proxies = ast.literal_eval(proxies_list[num])
    resp = requests.get(url=url, headers=headers, proxies=proxies)
    resp.encoding = 'utf-8'
    # print(resp.text)
    tree = etree.HTML(resp.text)
    nodes1 = tree.xpath(f"//a[@class]/@href")
    pattern = r'^/.+/\w+/\w+/\d+$'
    matched_strings = [s for s in nodes1 if re.search(pattern, s)]
    matched_strings = set(matched_strings)
    for y in matched_strings:
        set1.add(r'https://github.com/' + y)


def main():
    set1 = set()
    one_urls = new_url()
    for x in one_urls:
        need_url(set1,x)
    for url in set1:
        print(url)



main()
