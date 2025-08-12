import time
import asyncio
import datetime
import json
from pathlib import Path
from typing import List, Tuple, Optional
from httpx import AsyncClient, TimeoutException, HTTPStatusError
from bs4 import BeautifulSoup
from astrbot.api import logger
import re

# 类型别名
ContestInfo = Tuple[str, str, str]  # [比赛名称, 比赛时间, 比赛链接]

class ContestDataManager:
    """比赛数据管理器"""

    def __init__(self, data_dir: str = "data"):
        """
        初始化数据管理器

        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.cache_file = self.data_dir / "contest_cache.json"

        # 使用固定的用户代理，避免依赖 fake-useragent
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # 初始化比赛数据
        self.cf: List[ContestInfo] = []
        self.nc: List[ContestInfo] = []
        self.atc: List[ContestInfo] = []

        # 加载缓存数据
        self._load_cache()

    def _load_cache(self) -> None:
        """加载缓存的比赛数据"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # 检查缓存是否过期（1小时）
                    cache_time = cache_data.get('timestamp', 0)
                    current_time = time.time()
                    if current_time - cache_time < 3600:  # 1小时内的缓存有效
                        self.cf = cache_data.get('cf', [])
                        self.nc = cache_data.get('nc', [])
                        self.atc = cache_data.get('atc', [])
                        logger.info("已加载缓存的比赛数据")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"加载缓存数据失败: {e}")

    def _save_cache(self) -> None:
        """保存比赛数据到缓存"""
        try:
            cache_data = {
                'timestamp': time.time(),
                'cf': self.cf,
                'nc': self.nc,
                'atc': self.atc
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except (OSError, IOError) as e:
            logger.error(f"保存缓存数据失败: {e}")

    async def get_data_cf(self, force_refresh: bool = False) -> bool:
        """
        获取Codeforces比赛数据

        Args:
            force_refresh: 是否强制刷新数据

        Returns:
            bool: 获取是否成功
        """
        if not force_refresh and self.cf:
            return True

        url = 'https://codeforces.com/api/contest.list?gym=false'
        max_retries = 3

        for attempt in range(max_retries):
            try:
                self.cf.clear()
                async with AsyncClient() as client:
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()

                data = response.json()
                if data.get('status') != 'OK':
                    logger.warning(f"CF API返回错误状态: {data.get('comment', 'Unknown error')}")
                    continue

                for contest in data['result']:
                    if contest['phase'] != "BEFORE":
                        break
                    contest_name = contest['name']
                    contest_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(contest['startTimeSeconds']))
                    contest_id = contest['id']
                    contest_url = f'https://codeforces.com/contest/{contest_id}'
                    self.cf.append([contest_name, contest_time, contest_url])

                self.cf.reverse()
                self._save_cache()
                logger.info(f"成功获取 {len(self.cf)} 场CF比赛数据")
                return True

            except (TimeoutException, HTTPStatusError) as e:
                logger.warning(f"获取CF比赛数据网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析CF比赛数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                logger.error(f"获取CF比赛数据未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避

        return False

    async def get_data_nc(self, force_refresh: bool = False) -> bool:
        """
        获取牛客比赛数据

        Args:
            force_refresh: 是否强制刷新数据

        Returns:
            bool: 获取是否成功
        """
        if not force_refresh and self.nc:
            return True

        url = 'https://ac.nowcoder.com/acm/calendar/contest'
        max_retries = 3

        for attempt in range(max_retries):
            try:
                date = f"{datetime.datetime.now().year} - {datetime.datetime.now().month}"
                timestamp = f'{time.time():.3f}'
                params = {
                    'token': '',
                    'month': date,
                    '_': timestamp
                }

                self.nc.clear()
                async with AsyncClient() as client:
                    response = await client.get(url, headers=self.headers, params=params, timeout=20.0)
                    response.raise_for_status()

                data = response.json()
                if data.get('msg') != "OK" or data.get('code') != 0:
                    logger.warning(f"牛客API返回错误: {data}")
                    continue

                current_timestamp = int(float(timestamp) * 1000)
                for contest in data.get("data", []):
                    if contest.get("startTime", 0) >= current_timestamp:
                        contest_name = contest.get("contestName", "")
                        contest_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(contest['startTime'] / 1000))
                        contest_url = contest.get("link", "")
                        self.nc.append([contest_name, contest_time, contest_url])

                self._save_cache()
                logger.info(f"成功获取 {len(self.nc)} 场牛客比赛数据")
                return True

            except (TimeoutException, HTTPStatusError) as e:
                logger.warning(f"获取牛客比赛数据网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析牛客比赛数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                logger.error(f"获取牛客比赛数据未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        return False

    async def get_data_atc(self, force_refresh: bool = False) -> bool:
        """
        获取AtCoder比赛数据

        Args:
            force_refresh: 是否强制刷新数据

        Returns:
            bool: 获取是否成功
        """
        if not force_refresh and self.atc:
            return True

        url = 'https://atcoder.jp/contests/?lang=en'
        max_retries = 3

        for attempt in range(max_retries):
            try:
                self.atc.clear()
                async with AsyncClient() as client:
                    response = await client.get(url=url, timeout=10.0)
                    response.raise_for_status()

                soup = BeautifulSoup(response.text, 'lxml')
                upcoming_table = soup.find('div', {'id': 'contest-table-upcoming'})
                if not upcoming_table:
                    logger.warning("未找到AtCoder即将举行的比赛表格")
                    continue

                tbody = upcoming_table.find('tbody')
                if not tbody:
                    logger.warning("AtCoder比赛表格为空")
                    continue

                cells = tbody.find_all('td')
                if len(cells) < 10:  # 至少需要两场比赛的数据
                    logger.warning("AtCoder比赛数据不足")
                    continue

                # 解析比赛数据
                contests_data = []
                for i in range(0, min(len(cells), 10), 5):  # 每场比赛占5个单元格
                    try:
                        # 比赛名称
                        name_cell = cells[i + 1]
                        contest_name = str(name_cell.find('a').get_text()).strip()

                        # 比赛链接
                        link_tag = name_cell.find('a')
                        contest_url = 'https://atcoder.jp' + link_tag.get('href')

                        # 比赛时间
                        time_cell = cells[i]
                        time_text = str(time_cell.find('time').get_text()).replace('+0900', '').strip()
                        contest_time = str(datetime.datetime.strptime(time_text, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
                        contest_time = contest_time[:-3]  # 移除秒数

                        contests_data.append([contest_name, contest_time, contest_url])

                    except (AttributeError, ValueError, IndexError) as e:
                        logger.warning(f"解析AtCoder比赛数据失败: {e}")
                        continue

                if contests_data:
                    self.atc = contests_data[:2]  # 只保留前两场比赛
                    self._save_cache()
                    logger.info(f"成功获取 {len(self.atc)} 场AtCoder比赛数据")
                    return True

            except (TimeoutException, HTTPStatusError) as e:
                logger.warning(f"获取AtCoder比赛数据网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                logger.error(f"获取AtCoder比赛数据未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        return False

    async def get_cf_info(self) -> str:
        """获取CF比赛信息字符串"""
        await self.get_data_cf()
        if not self.cf:
            return '突然出错了，稍后再试哦~'

        msg_parts = []
        for i, contest in enumerate(self.cf[:3]):  # 最多显示3场比赛
            contest_info = f"比赛名称：{contest[0]}\n比赛时间：{contest[1]}\n比赛链接：{contest[2]}"
            msg_parts.append(contest_info)

        return f"找到最近的 {len(msg_parts)} 场CF比赛为：\n\n" + "\n\n".join(msg_parts)

    async def get_nc_info(self) -> str:
        """获取牛客比赛信息字符串"""
        await self.get_data_nc()
        if not self.nc:
            return '突然出错了，稍后再试哦~'

        msg_parts = []
        for i, contest in enumerate(self.nc[:3]):  # 最多显示3场比赛
            contest_info = f"比赛名称：{contest[0]}\n比赛时间：{contest[1]}\n比赛链接：{contest[2]}"
            msg_parts.append(contest_info)

        return f"找到最近的 {len(msg_parts)} 场牛客比赛为：\n\n" + "\n\n".join(msg_parts)

    async def get_atc_info(self) -> str:
        """获取AtCoder比赛信息字符串"""
        await self.get_data_atc()
        if not self.atc:
            return '突然出错了，稍后再试哦~'

        if len(self.atc) >= 2:
            return (f"找到最近的 2 场AtCoder比赛为：\n\n"
                   f"比赛名称：{self.atc[0][0]}\n比赛时间：{self.atc[0][1]}\n比赛链接：{self.atc[0][2]}\n\n"
                   f"比赛名称：{self.atc[1][0]}\n比赛时间：{self.atc[1][1]}\n比赛链接：{self.atc[1][2]}")
        elif len(self.atc) == 1:
            return (f"找到 1 场AtCoder比赛为：\n\n"
                   f"比赛名称：{self.atc[0][0]}\n比赛时间：{self.atc[0][1]}\n比赛链接：{self.atc[0][2]}")
        else:
            return '暂无AtCoder比赛数据'

    async def get_today_info(self) -> str:
        """获取今日比赛信息"""
        # 并发获取所有平台数据
        await asyncio.gather(
            self.get_data_cf(),
            self.get_data_nc(),
            self.get_data_atc(),
            return_exceptions=True
        )

        today = datetime.datetime.now().date()
        msg_parts = []

        # 检查各平台今日比赛
        for platform, contests, name in [
            ("Codeforces", self.cf, "◉Codeforces比赛："),
            ("牛客", self.nc, "◉牛客比赛："),
            ("AtCoder", self.atc, "◉AtCoder比赛：")
        ]:
            platform_contests = []
            for contest in contests:
                try:
                    contest_date = datetime.datetime.strptime(contest[1], "%Y-%m-%d %H:%M").date()
                    if contest_date == today:
                        contest_info = f"比赛名称：{contest[0]}\n比赛时间：{contest[1]}\n比赛链接：{contest[2]}"
                        platform_contests.append(contest_info)
                except ValueError as e:
                    logger.warning(f"解析{platform}比赛时间失败: {e}")
                    continue

            if platform_contests:
                msg_parts.append(name + "\n" + "\n\n".join(platform_contests))

        if not any([self.cf, self.nc, self.atc]):
            return '查询出错了，稍后再尝试哦~'

        if not msg_parts:
            return '今天没有比赛，但也要好好做题哦~'

        return '找到今天的比赛如下：\n\n' + '\n\n'.join(msg_parts)

# 全局数据管理器实例
contest_manager = ContestDataManager()

# 兼容性函数
async def ans_cf() -> str:
    """获取CF比赛信息（兼容性函数）"""
    return await contest_manager.get_cf_info()

async def ans_nc() -> str:
    """获取牛客比赛信息（兼容性函数）"""
    return await contest_manager.get_nc_info()

async def ans_atc() -> str:
    """获取AtCoder比赛信息（兼容性函数）"""
    return await contest_manager.get_atc_info()

async def ans_today() -> str:
    """获取今日比赛信息（兼容性函数）"""
    return await contest_manager.get_today_info()
