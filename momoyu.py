import requests
import re
from bs4 import BeautifulSoup
import openai
import asyncio
import aiohttp

# 设置你的OpenAI API密钥
openai.api_key = '!!!!'

def get_rss_content(url):
    """获取RSS链接的实时内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"获取RSS内容时出错: {e}")
        return None

async def get_emoji_for_title(title, client_session):
    """使用GPT-4为标题生成合适的emoji"""
    try:
        async with client_session.post(
            "!!!!",
            headers={
                "Authorization": f"Bearer {openai.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "system",
                    "content": "你是一个emoji助手。请为给定的新闻标题选择一个最合适的emoji。只返回emoji，不要其他文字。"
                }, {
                    "role": "user",
                    "content": title
                }],
                "max_tokens": 10
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                emoji = data['choices'][0]['message']['content'].strip()
                return f"{emoji} {title}"
            return title
    except Exception as e:
        print(f"获取emoji时出错: {e}")
        return title

async def process_titles(titles, category):
    """异步处理一组标题"""
    async with aiohttp.ClientSession() as session:
        tasks = [get_emoji_for_title(title, session) for title in titles]
        return await asyncio.gather(*tasks)

def parse_xml_content(xml_content):
    """解析XML内容并提取不同类别的热搜标题"""
    try:
        # 使用BeautifulSoup解析XML内容
        soup = BeautifulSoup(xml_content, 'xml')  # 使用xml解析器
        
        # 找到item下的description标签
        description = soup.find('item').find('description').text
        
        # 解析description中的HTML内容
        content_soup = BeautifulSoup(description, 'html.parser')
        
        # 初始化结果字典
        results = {
            '微博热搜': [],
            '爱范儿': [],
            '游戏喜加一': []
        }
        
        # 查找所有的标题和链接
        current_category = None
        for element in content_soup.find_all(['h2', 'p']):
            if element.name == 'h2':
                current_category = element.text.strip()
                print(f"找到分类: {current_category}")
            elif element.name == 'p' and current_category:
                link = element.find('a')
                if link:
                    # 提取标题文本（去除序号）
                    title = re.sub(r'^\d+\.\s*', '', link.text.strip())
                    if current_category in results:
                        results[current_category].append(title)
        
        # 打印调试信息
        for category, titles in results.items():
            print(f"{category}: {len(titles)} 条标题")
        
        return results
        
    except Exception as e:
        print(f"解析内容时出错: {e}")
        print("错误发生在以下内容处理时:")
        print(xml_content[:200] + "...")  # 打印前200个字符用于调试
        return None

async def main():
    # RSS源URL
    rss_url = "!!!!"
    
    # 获取RSS内容
    xml_content = get_rss_content(rss_url)
    if not xml_content:
        print("无法获取RSS内容")
        return
        
    # 解析XML内容
    categories = parse_xml_content(xml_content)
    
    if not categories:
        print("无法获取分类数据")
        return
    
    # 为每个类别的标题添加emoji
    for category, titles in categories.items():
        if titles:
            print(f"\n=== {category} ===")
            processed_titles = await process_titles(titles, category)
            for title in processed_titles:
                print(title)

if __name__ == "__main__":
    asyncio.run(main())
