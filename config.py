from pydantic import BaseModel
from typing import List, Dict
import json
import os
from pathlib import Path

class Config(BaseModel):
    # 比赛提醒时间配置 (小时:分钟)
    matchreminder_time: Dict[str, str] = {"hour": "8", "minute": "30"}
    # 发送每日比赛提醒的群聊ID列表
    matchreminder_list: List[str] = []
    # 是否启用定时提醒功能
    enable_auto_reminder: bool = False

class ConfigManager:
    def __init__(self, data_dir: str = "data"):
        """
        初始化配置管理器

        Args:
            data_dir: 数据目录路径，遵循AstrBot插件开发原则
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)  # 确保data目录存在
        self.config_path = self.data_dir / "config.json"
        self.config = self.load_config()

    def load_config(self) -> Config:
        """
        加载配置文件

        Returns:
            Config: 配置对象
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return Config(**data)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                # 配置文件损坏时使用默认配置
                return Config()
        return Config()

    def save_config(self) -> bool:
        """
        保存配置文件

        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config.dict(), f, indent=2, ensure_ascii=False)
            return True
        except (OSError, IOError) as e:
            return False

    def add_group(self, group_id: str) -> bool:
        """
        添加群聊到提醒列表

        Args:
            group_id: 群聊ID

        Returns:
            bool: 添加是否成功
        """
        if group_id not in self.config.matchreminder_list:
            self.config.matchreminder_list.append(group_id)
            return self.save_config()
        return False

    def remove_group(self, group_id: str) -> bool:
        """
        从提醒列表中移除群聊

        Args:
            group_id: 群聊ID

        Returns:
            bool: 移除是否成功
        """
        if group_id in self.config.matchreminder_list:
            self.config.matchreminder_list.remove(group_id)
            return self.save_config()
        return False

    def set_reminder_time(self, hour: str, minute: str) -> bool:
        """
        设置提醒时间

        Args:
            hour: 小时
            minute: 分钟

        Returns:
            bool: 设置是否成功
        """
        try:
            # 验证时间格式
            hour_int = int(hour)
            minute_int = int(minute)
            if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
                return False

            self.config.matchreminder_time = {"hour": hour, "minute": minute}
            return self.save_config()
        except ValueError:
            return False

    def toggle_auto_reminder(self) -> bool:
        """
        切换自动提醒开关

        Returns:
            bool: 切换后的状态
        """
        self.config.enable_auto_reminder = not self.config.enable_auto_reminder
        self.save_config()
        return self.config.enable_auto_reminder

# 全局配置实例
config_manager = ConfigManager()
