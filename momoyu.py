import requests
import re
from bs4 import BeautifulSoup
import asyncio
import aiohttp
import plugins
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger

@plugins.register(
    name="momoyu",
    desc="一款基于摸摸鱼标题提取的插件",
    version="1.0",
    author="SpaceX",
    desire_priority=90
)
class momoyu(Plugin):
    content = None

    def __init__(self):
        super().__init__()
        self.config = super().load_config()
        self.api_base = self.config.get("api_base", "")
        self.api_key = self.config.get("api_key", "")
        self.rss = self.config.get("rss", "")
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info(f"[{__class__.__name__}] initialized")

    def get_help_text(self, **kwargs):
        return "发送【新闻】获取最新热点新闻并自动生成表情符号！"

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return
        self.content = e_context["context"].content.strip()

        if self.content == "新闻":
            logger.info(f"[{__class__.__name__}] 收到消息: {self.content}")
            reply = Reply()
            reply.content = ""

            # 获取RSS内容
            xml_content = self.get_rss_content(self.rss)
            if not xml_content:
                reply.type = ReplyType.ERROR
                reply.content = "无法获取RSS内容，请稍后重试。"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return

            # 解析内容
            categories = self.parse_xml_content(xml_content)
            if not categories:
                reply.type = ReplyType.ERROR
                reply.content = "解析RSS内容失败。"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return

            # 为每个标题添加emoji
            asyncio.run(self.process_categories(reply, categories, e_context))

    def get_rss_content(self, url):
        """获取RSS链接的实时内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取RSS内容时出错: {e}")
            return None

    def parse_xml_content(self, xml_content):
        """解析XML内容并提取不同类别的热搜标题"""
        try:
            soup = BeautifulSoup(xml_content, 'xml')
            item = soup.find('item')
            if not item or not item.find('description'):
                logger.warning("未找到有效的item或description")
                return None

            description = item.find('description').text
            content_soup = BeautifulSoup(description, 'html.parser')

            results = {'微博热搜': [], '爱范儿': [], '游戏喜加一': []}
            current_category = None

            for element in content_soup.find_all(['h2', 'p']):
                if element.name == 'h2':
                    current_category = element.text.strip()
                elif element.name == 'p' and current_category:
                    link = element.find('a')
                    if link:
                        title = re.sub(r'^\d+\.\s*', '', link.text.strip())
                        if current_category in results:
                            results[current_category].append(title)
            return results
        except Exception as e:
            logger.error(f"解析内容时出错: {e}")
            return None

    async def get_emoji_for_title(self, title, client_session):
        """使用GPT-4o-mini为标题生成合适的emoji"""
        try:
            async with client_session.post(
                url=f"{self.api_base}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
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
            logger.error(f"获取emoji时出错: {e}")
            return title

    async def process_titles(self, titles, client_session):
        """异步处理一组标题"""
        tasks = [self.get_emoji_for_title(title, client_session) for title in titles]
        return await asyncio.gather(*tasks)

    async def process_categories(self, reply, categories, e_context):
        """为每个类别的标题添加emoji"""
        async with aiohttp.ClientSession() as session:
            result = ""
            for category, titles in categories.items():
                if titles:
                    processed_titles = await self.process_titles(titles, session)
                    result += f"\n\n=== {category} ===\n" + "\n".join(processed_titles)
                    reply = Reply(ReplyType.TEXT, f"{result}")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
