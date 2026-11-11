"""Cloud Auto Task Demo：一个最小可用的云端定时任务项目。

模块划分（对应 GitHub Actions 的职责边界）：
- config.py   读取配置（决定"跑什么"）
- task.py     具体业务逻辑（决定"怎么跑"）
- notifier.py 结果通知（把"跑完了"告诉人）
- main.py     程序入口（把上面三步串起来，返回退出码）
"""

__version__ = "0.1.0"
