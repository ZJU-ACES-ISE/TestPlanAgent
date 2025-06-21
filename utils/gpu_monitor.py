#!/usr/bin/env python3
"""
GPU监控脚本 - 当至少2个GPU空闲时发送邮件通知
需要安装: pip install nvidia-ml-py3
"""

import time
import subprocess
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple

# 尝试导入邮件相关模块，如果失败则使用替代方案
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_AVAILABLE = True
except ImportError as e:
    print(f"邮件模块导入失败: {e}")
    print("将使用系统命令发送邮件")
    EMAIL_AVAILABLE = False

# ========== 配置区域 ==========
# 邮件配置
SMTP_SERVER = "smtp.gmail.com"  # Gmail SMTP，根据你的邮箱提供商修改
SMTP_PORT = 465
SENDER_EMAIL = "q1040242795@gmail.com"  # 发送者邮箱
SENDER_PASSWORD = "uqgkpyvtxkknrmcn"  # 应用专用密码，不是邮箱密码
RECEIVER_EMAIL = "q1040242795@gmail.com"  # 接收者邮箱

# GPU监控配置
MIN_FREE_GPUS = 2  # 最少空闲GPU数量
GPU_UTIL_THRESHOLD = 10  # GPU利用率阈值（%），低于此值认为空闲
MEMORY_UTIL_THRESHOLD = 10  # 显存利用率阈值（%），低于此值认为空闲
CHECK_INTERVAL = 60  # 检查间隔（秒）
NOTIFICATION_COOLDOWN = 1800  # 通知冷却时间（秒），避免重复通知

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gpu_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GPUMonitor:
    def __init__(self):
        self.last_notification_time = 0
        self.notification_sent = False
        
    def get_gpu_info(self) -> List[Dict]:
        """获取GPU信息"""
        try:
            # 使用nvidia-smi获取GPU信息
            cmd = [
                "nvidia-smi", 
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 7:
                        gpu_info = {
                            'index': int(parts[0]),
                            'name': parts[1],
                            'utilization': float(parts[2]) if parts[2] != '[Not Supported]' else 0,
                            'memory_used': int(parts[3]),
                            'memory_total': int(parts[4]),
                            'temperature': float(parts[5]) if parts[5] != '[Not Supported]' else 0,
                            'power_draw': float(parts[6]) if parts[6] != '[Not Supported]' else 0
                        }
                        gpu_info['memory_util'] = (gpu_info['memory_used'] / gpu_info['memory_total']) * 100
                        gpus.append(gpu_info)
            
            return gpus
            
        except subprocess.CalledProcessError as e:
            logger.error(f"获取GPU信息失败: {e}")
            return []
        except Exception as e:
            logger.error(f"解析GPU信息时出错: {e}")
            return []
    
    def is_gpu_idle(self, gpu: Dict) -> bool:
        """判断GPU是否空闲"""
        return (gpu['utilization'] < GPU_UTIL_THRESHOLD and 
                gpu['memory_util'] < MEMORY_UTIL_THRESHOLD)
    
    def get_idle_gpus(self, gpus: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """获取空闲和忙碌的GPU列表"""
        idle_gpus = [gpu for gpu in gpus if self.is_gpu_idle(gpu)]
        busy_gpus = [gpu for gpu in gpus if not self.is_gpu_idle(gpu)]
        return idle_gpus, busy_gpus
    
    def send_email_notification(self, idle_gpus: List[Dict], busy_gpus: List[Dict]):
        """发送邮件通知"""
        try:
            subject = f"🚀 GPU可用通知 - {len(idle_gpus)}个GPU空闲"
            
            if EMAIL_AVAILABLE:
                # 使用Python内置邮件模块
                self._send_email_python(subject, idle_gpus, busy_gpus)
            else:
                # 使用系统邮件命令
                self._send_email_system(subject, idle_gpus, busy_gpus)
                
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
    
    def _send_email_python(self, subject: str, idle_gpus: List[Dict], busy_gpus: List[Dict]):
        """使用Python内置模块发送邮件"""
        # HTML邮件内容
        html_content = f"""
        <html>
        <body>
            <h2>🖥️ GPU状态监控报告</h2>
            <p><strong>时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>服务器:</strong> {subprocess.getoutput('hostname')}</p>
            
            <h3>✅ 空闲GPU ({len(idle_gpus)}个):</h3>
            <table border="1" style="border-collapse: collapse; margin: 10px 0;">
                <tr style="background-color: #f0f0f0;">
                    <th>GPU</th><th>型号</th><th>利用率</th><th>显存使用</th><th>温度</th><th>功耗</th>
                </tr>
        """
        
        for gpu in idle_gpus:
            html_content += f"""
                <tr style="background-color: #e8f5e8;">
                    <td>GPU {gpu['index']}</td>
                    <td>{gpu['name']}</td>
                    <td>{gpu['utilization']:.1f}%</td>
                    <td>{gpu['memory_used']}/{gpu['memory_total']}MB ({gpu['memory_util']:.1f}%)</td>
                    <td>{gpu['temperature']:.1f}°C</td>
                    <td>{gpu['power_draw']:.1f}W</td>
                </tr>
            """
        
        html_content += "</table>"
        
        if busy_gpus:
            html_content += f"""
            <h3>🔥 忙碌GPU ({len(busy_gpus)}个):</h3>
            <table border="1" style="border-collapse: collapse; margin: 10px 0;">
                <tr style="background-color: #f0f0f0;">
                    <th>GPU</th><th>型号</th><th>利用率</th><th>显存使用</th><th>温度</th><th>功耗</th>
                </tr>
            """
            
            for gpu in busy_gpus:
                html_content += f"""
                    <tr style="background-color: #ffe8e8;">
                        <td>GPU {gpu['index']}</td>
                        <td>{gpu['name']}</td>
                        <td>{gpu['utilization']:.1f}%</td>
                        <td>{gpu['memory_used']}/{gpu['memory_total']}MB ({gpu['memory_util']:.1f}%)</td>
                        <td>{gpu['temperature']:.1f}°C</td>
                        <td>{gpu['power_draw']:.1f}W</td>
                    </tr>
                """
            
            html_content += "</table>"
        
        html_content += """
            <p style="color: #666; font-size: 12px;">
                此邮件由GPU监控脚本自动发送<br>
                如需停止监控，请终止相应的Python进程
            </p>
        </body>
        </html>
        """
        
        # 创建邮件
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # 发送邮件
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"邮件通知已发送到 {RECEIVER_EMAIL}")
    
    def _send_email_system(self, subject: str, idle_gpus: List[Dict], busy_gpus: List[Dict]):
        """使用系统命令发送邮件"""
        # 构建邮件内容
        content = f"""GPU状态监控报告

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
服务器: {subprocess.getoutput('hostname')}

✅ 空闲GPU ({len(idle_gpus)}个):
"""
        
        for gpu in idle_gpus:
            content += f"GPU {gpu['index']} ({gpu['name']}): {gpu['utilization']:.1f}% 利用率, {gpu['memory_used']}/{gpu['memory_total']}MB ({gpu['memory_util']:.1f}%) 显存, {gpu['temperature']:.1f}°C, {gpu['power_draw']:.1f}W\n"
        
        if busy_gpus:
            content += f"\n🔥 忙碌GPU ({len(busy_gpus)}个):\n"
            for gpu in busy_gpus:
                content += f"GPU {gpu['index']} ({gpu['name']}): {gpu['utilization']:.1f}% 利用率, {gpu['memory_used']}/{gpu['memory_total']}MB ({gpu['memory_util']:.1f}%) 显存, {gpu['temperature']:.1f}°C, {gpu['power_draw']:.1f}W\n"
        
        content += "\n此邮件由GPU监控脚本自动发送"
        
        # 尝试使用不同的邮件命令
        try:
            # 方法1: 使用mailx
            cmd = ['mailx', '-s', subject, RECEIVER_EMAIL]
            result = subprocess.run(cmd, input=content, text=True, capture_output=True)
            if result.returncode == 0:
                logger.info(f"通过mailx发送邮件到 {RECEIVER_EMAIL}")
                return
        except FileNotFoundError:
            pass
        
        try:
            # 方法2: 使用mail
            cmd = ['mail', '-s', subject, RECEIVER_EMAIL]
            result = subprocess.run(cmd, input=content, text=True, capture_output=True)
            if result.returncode == 0:
                logger.info(f"通过mail发送邮件到 {RECEIVER_EMAIL}")
                return
        except FileNotFoundError:
            pass
        
        try:
            # 方法3: 使用sendmail
            sendmail_content = f"""Subject: {subject}
To: {RECEIVER_EMAIL}
From: {SENDER_EMAIL}

{content}"""
            
            cmd = ['sendmail', RECEIVER_EMAIL]
            result = subprocess.run(cmd, input=sendmail_content, text=True, capture_output=True)
            if result.returncode == 0:
                logger.info(f"通过sendmail发送邮件到 {RECEIVER_EMAIL}")
                return
        except FileNotFoundError:
            pass
        
        # 如果所有邮件命令都失败，记录到日志
        logger.warning("无法发送邮件，将通知内容记录到日志:")
        logger.info(f"=== {subject} ===")
        logger.info(content)
        logger.info("=" * 50)
    
    def monitor_loop(self):
        """主监控循环"""
        logger.info("GPU监控开始运行...")
        logger.info(f"监控配置: 最少空闲GPU数={MIN_FREE_GPUS}, GPU利用率阈值={GPU_UTIL_THRESHOLD}%, 显存阈值={MEMORY_UTIL_THRESHOLD}%")
        
        while True:
            try:
                gpus = self.get_gpu_info()
                if not gpus:
                    logger.warning("未获取到GPU信息，跳过本次检查")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                idle_gpus, busy_gpus = self.get_idle_gpus(gpus)
                current_time = time.time()
                
                # 日志记录当前状态
                logger.info(f"GPU状态: {len(idle_gpus)}个空闲, {len(busy_gpus)}个忙碌")
                
                # 检查是否满足通知条件
                if len(idle_gpus) >= MIN_FREE_GPUS:
                    # 检查冷却时间
                    if (current_time - self.last_notification_time) > NOTIFICATION_COOLDOWN:
                        logger.info(f"检测到{len(idle_gpus)}个GPU空闲，发送通知...")
                        self.send_email_notification(idle_gpus, busy_gpus)
                        self.last_notification_time = current_time
                        self.notification_sent = True
                    else:
                        remaining_cooldown = NOTIFICATION_COOLDOWN - (current_time - self.last_notification_time)
                        logger.info(f"GPU仍然空闲，但在冷却期内 (剩余 {remaining_cooldown:.0f} 秒)")
                else:
                    if self.notification_sent:
                        logger.info("GPU已被占用，重置通知状态")
                        self.notification_sent = False
                
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("监控已停止")
                break
            except Exception as e:
                logger.error(f"监控循环中出现错误: {e}")
                time.sleep(CHECK_INTERVAL)

def main():
    # 验证邮件配置
    if SENDER_EMAIL == "your_email@gmail.com" or RECEIVER_EMAIL == "receiver@gmail.com":
        print("⚠️  请先配置邮件信息!")
        print("修改脚本中的 SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL")
        print("\n对于Gmail用户:")
        print("1. 启用两步验证")
        print("2. 生成应用专用密码: https://support.google.com/accounts/answer/185833")
        print("3. 使用应用专用密码作为 SENDER_PASSWORD")
        return
    
    monitor = GPUMonitor()
    monitor.monitor_loop()

if __name__ == "__main__":
    main()