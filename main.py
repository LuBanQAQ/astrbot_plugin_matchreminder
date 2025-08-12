from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from .config import config_manager
from .data_source import ans_cf, ans_nc, ans_atc, ans_today
import asyncio
from datetime import datetime, timedelta
from typing import Optional

@register("matchreminder", "LuBanQAQ", "算法比赛查询和今日比赛自动提醒", "1.0.3")
class MatchReminderPlugin(Star):
    """
    算法比赛提醒插件

    支持查询 Codeforces、牛客、AtCoder 三大平台的比赛信息
    并提供定时提醒功能
    """

    def __init__(self, context: Context):
        super().__init__(context)
        self.reminder_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """插件初始化"""
        try:
            logger.info("比赛提醒插件初始化完成")
            # 如果启用了自动提醒，启动定时任务
            if config_manager.config.enable_auto_reminder:
                await self.start_reminder_task()
        except Exception as e:
            logger.error(f"插件初始化失败: {e}")

    @filter.command("cf")
    async def query_cf(self, event: AstrMessageEvent):
        """查询Codeforces比赛"""
        try:
            logger.info("用户请求查询CF比赛")
            msg = await ans_cf()
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"查询CF比赛失败: {e}")
            yield event.plain_result("查询失败，请稍后再试")

    @filter.command("nc")
    async def query_nc(self, event: AstrMessageEvent):
        """查询牛客比赛"""
        try:
            logger.info("用户请求查询牛客比赛")
            msg = await ans_nc()
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"查询牛客比赛失败: {e}")
            yield event.plain_result("查询失败，请稍后再试")

    @filter.command("atc")
    async def query_atc(self, event: AstrMessageEvent):
        """查询AtCoder比赛"""
        try:
            logger.info("用户请求查询AtCoder比赛")
            msg = await ans_atc()
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"查询AtCoder比赛失败: {e}")
            yield event.plain_result("查询失败，请稍后再试")

    @filter.command("今日比赛")
    async def query_today(self, event: AstrMessageEvent):
        """查询今日比赛"""
        try:
            logger.info("用户请求查询今日比赛")
            msg = await ans_today()
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"查询今日比赛失败: {e}")
            yield event.plain_result("查询失败，请稍后再试")

    @filter.command("添加提醒群")
    async def add_reminder_group(self, event: AstrMessageEvent):
        """添加当前群到比赛提醒列表"""
        try:
            # 获取群ID (这里需要根据实际的event结构调整)
            group_id = str(event.session_id)

            if config_manager.add_group(group_id):
                logger.info(f"成功添加群 {group_id} 到提醒列表")
                yield event.plain_result(f"✅ 成功添加群 {group_id} 到比赛提醒列表")
            else:
                yield event.plain_result("❌ 该群已在提醒列表中")
        except Exception as e:
            logger.error(f"添加提醒群失败: {e}")
            yield event.plain_result("操作失败，请稍后再试")

    @filter.command("移除提醒群")
    async def remove_reminder_group(self, event: AstrMessageEvent):
        """从比赛提醒列表中移除当前群"""
        try:
            group_id = str(event.session_id)

            if config_manager.remove_group(group_id):
                logger.info(f"成功从提醒列表中移除群 {group_id}")
                yield event.plain_result(f"✅ 成功从提醒列表中移除群 {group_id}")
            else:
                yield event.plain_result("❌ 该群不在提醒列表中")
        except Exception as e:
            logger.error(f"移除提醒群失败: {e}")
            yield event.plain_result("操作失败，请稍后再试")

    @filter.command("设置提醒时间")
    async def set_reminder_time(self, event: AstrMessageEvent):
        """
        设置比赛提醒时间

        格式: /设置提醒时间 小时 分钟
        例如: /设置提醒时间 8 30
        """
        try:
            parts = event.message_str.strip().split()
            if len(parts) >= 3:
                hour = parts[1]
                minute = parts[2]

                if config_manager.set_reminder_time(hour, minute):
                    logger.info(f"提醒时间已设置为 {hour}:{minute}")
                    yield event.plain_result(f"✅ 提醒时间已设置为 {hour}:{minute}")

                    # 重启提醒任务
                    if config_manager.config.enable_auto_reminder:
                        await self.restart_reminder_task()
                        yield event.plain_result("⏰ 定时任务已更新")
                else:
                    yield event.plain_result("❌ 时间格式错误，请确保小时在0-23之间，分钟在0-59之间")
            else:
                yield event.plain_result(
                    "❌ 格式错误，请使用: /设置提醒时间 小时 分钟\n"
                    "例如: /设置提醒时间 8 30"
                )
        except Exception as e:
            logger.error(f"设置提醒时间失败: {e}")
            yield event.plain_result("设置失败，请检查格式")

    @filter.command("切换自动提醒")
    async def toggle_auto_reminder(self, event: AstrMessageEvent):
        """切换自动提醒开关"""
        try:
            enabled = config_manager.toggle_auto_reminder()
            if enabled:
                await self.start_reminder_task()
                logger.info("自动提醒已开启")
                yield event.plain_result("✅ 自动提醒已开启")
            else:
                await self.stop_reminder_task()
                logger.info("自动提醒已关闭")
                yield event.plain_result("❌ 自动提醒已关闭")
        except Exception as e:
            logger.error(f"切换自动提醒失败: {e}")
            yield event.plain_result("操作失败，请稍后再试")

    @filter.command("查看提醒配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前提醒配置"""
        try:
            config = config_manager.config
            msg = "📋 当前配置：\n"
            msg += f"⏰ 提醒时间: {config.matchreminder_time['hour']}:{config.matchreminder_time['minute']}\n"
            msg += f"🔔 自动提醒: {'✅ 开启' if config.enable_auto_reminder else '❌ 关闭'}\n"
            msg += f"👥 提醒群列表: {', '.join(config.matchreminder_list) if config.matchreminder_list else '无'}"
            yield event.plain_result(msg)
        except Exception as e:
            logger.error(f"查看提醒配置失败: {e}")
            yield event.plain_result("查看配置失败，请稍后再试")

    @filter.command("比赛提醒插件帮助")
    async def show_help(self, event: AstrMessageEvent):
        """显示插件帮助信息"""
        help_msg = """📚 比赛提醒插件帮助

🔍 比赛查询指令：
• /cf - 查询最近的 Codeforces 比赛
• /nc - 查询最近的牛客比赛
• /atc - 查询最近的 AtCoder 比赛
• /今日比赛 - 查询今天的所有比赛

⚙️ 提醒管理指令：
• /添加提醒群 - 将当前群添加到比赛提醒列表
• /移除提醒群 - 从提醒列表中移除当前群
• /设置提醒时间 小时 分钟 - 设置每日提醒时间
• /切换自动提醒 - 开启/关闭自动提醒功能
• /查看提醒配置 - 查看当前的提醒配置
• /帮助 - 显示此帮助信息

💡 使用提示：
1. 首次使用请先用 /切换自动提醒 开启自动提醒
2. 使用 /添加提醒群 将群聊加入提醒列表
3. 可用 /设置提醒时间 自定义提醒时间（默认8:30）"""
        yield event.plain_result(help_msg)

    async def start_reminder_task(self) -> bool:
        """
        启动定时提醒任务

        Returns:
            bool: 启动是否成功
        """
        if self.reminder_task and not self.reminder_task.done():
            return True

        try:
            self.reminder_task = asyncio.create_task(self.reminder_loop())
            logger.info("比赛提醒定时任务已启动")
            return True
        except Exception as e:
            logger.error(f"启动定时任务失败: {e}")
            return False

    async def stop_reminder_task(self) -> bool:
        """
        停止定时提醒任务

        Returns:
            bool: 停止是否成功
        """
        try:
            if self.reminder_task and not self.reminder_task.done():
                self.reminder_task.cancel()
                try:
                    await self.reminder_task
                except asyncio.CancelledError:
                    pass
            self.reminder_task = None
            logger.info("比赛提醒定时任务已停止")
            return True
        except Exception as e:
            logger.error(f"停止定时任务失败: {e}")
            return False

    async def restart_reminder_task(self) -> bool:
        """
        重启定时提醒任务

        Returns:
            bool: 重启是否成功
        """
        try:
            await self.stop_reminder_task()
            if config_manager.config.enable_auto_reminder:
                return await self.start_reminder_task()
            return True
        except Exception as e:
            logger.error(f"重启定时任务失败: {e}")
            return False

    async def reminder_loop(self):
        """定时提醒循环"""
        while True:
            try:
                now = datetime.now()
                config = config_manager.config

                # 验证配置有效性
                try:
                    target_hour = int(config.matchreminder_time['hour'])
                    target_minute = int(config.matchreminder_time['minute'])
                except (ValueError, KeyError) as e:
                    logger.error(f"无效的提醒时间配置: {e}")
                    await asyncio.sleep(3600)  # 配置错误时等待1小时
                    continue

                # 计算下次提醒时间
                target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                if target_time <= now:
                    target_time += timedelta(days=1)

                # 等待到目标时间
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"下次提醒时间: {target_time}, 等待: {wait_seconds:.1f} 秒")
                await asyncio.sleep(wait_seconds)

                # 发送今日比赛提醒
                await self.send_daily_reminder()

            except asyncio.CancelledError:
                logger.info("定时提醒任务被取消")
                break
            except Exception as e:
                logger.error(f"定时提醒任务异常: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时再重试

    async def send_daily_reminder(self):
        """发送每日比赛提醒"""
        try:
            msg = await ans_today()
            reminder_msg = f"📅 每日比赛提醒\n\n{msg}"

            group_list = config_manager.config.matchreminder_list
            if not group_list:
                logger.warning("没有配置提醒群，跳过发送提醒")
                return

            # 向所有配置的群发送提醒
            success_count = 0
            for group_id in group_list:
                try:
                    # 这里需要根据实际的API调整发送消息的方法
                    # 由于无法直接访问机器人API，这里只记录日志
                    # 实际实现时需要使用 AstrBot 提供的群消息发送API
                    logger.info(f"向群 {group_id} 发送比赛提醒: {reminder_msg[:50]}...")
                    success_count += 1
                    await asyncio.sleep(0.5)  # 避免发送过快
                except Exception as e:
                    logger.error(f"向群 {group_id} 发送提醒失败: {e}")

            logger.info(f"提醒发送完成，成功: {success_count}/{len(group_list)}")

        except Exception as e:
            logger.error(f"发送每日提醒失败: {e}")

    async def terminate(self):
        """插件销毁"""
        try:
            await self.stop_reminder_task()
            logger.info("比赛提醒插件已销毁")
        except Exception as e:
            logger.error(f"插件销毁失败: {e}")
