# Autumn Job Tracker · 秋招投递看板

在自己的电脑上管理岗位、简历版本和投递进展。下载代码后，用 Python 启动并在浏览器操作；数据保存在本机文件夹。

## 功能

- 岗位详情、网页申请入口、匹配理由、短板和简历版本放在同一张卡片。
- 登记真实提交；按北京时间统计今天、近7天、累计数量与每日明细。
- 已投岗位自动从待投清单隐藏；重复登记不重复计数。
- 保留投递时的岗位信息、匹配分析和简历修改快照。
- 满7天仍无实质回复的申请进入复盘列表；自动回执不算实质进展。
- 手动添加岗位，导入/导出岗位库，补录其他渠道的投递，更新进度。
- 每次写入保存最近一份备份；误登记可撤销，撤销记录仍保留。
- 网页按钮只接受HTTP/HTTPS地址；邮件渠道单独列出。

## 运行要求

Python **3.10或以上**和常用浏览器。使用Python标准库，无需安装 pip/npm 依赖；界面没有CDN资源、外部字体、账号登录或遥测。

### Windows

1. 安装 [Python](https://www.python.org/downloads/)，安装时启用 PATH 或 Python Launcher。
2. 从GitHub选择 **Code → Download ZIP**，解压到任意目录。
3. 双击 `start-windows.cmd`，浏览器会打开 `http://127.0.0.1:18728/`。
4. 保留启动窗口；关闭窗口或按 `Ctrl+C` 停止服务。

也可以运行：

```powershell
python app.py --open
```

### macOS / Linux

```sh
sh start.sh
# 或
python3 app.py --open
```

电脑安装好Python、项目下载完成后，查看/登记/统计/导入导出均可离线使用。打开企业招聘网页仍需要联网。

## 接入已有数据

默认首次启动只创建空白 `data/`，没有真实申请或个人资料。

已有目录包含 `岗位库.json` 和 `投递记录.json` 时，可以直接指定：

```powershell
python app.py --data-dir "E:\面试" --open
```

已有文件不会被初始化覆盖。运行后在页面右上角检查当前数据目录。原有 `原版简历/`、`简历定制/` 相对链接继续有效。使用同一个数据目录时，关闭旧版服务，避免两个程序同时写入。

也可以复制 `config.example.json` 为 `config.json`，设置：

```json
{"data_dir": "E:/面试"}
```

`config.json` 和 `data/` 已加入Git忽略。修改端口使用 `--port 18729`；软件始终只监听本机回环地址。

## 添加岗位与简历

1. 点击“添加岗位”，输入公司、岗位、直达网页、岗位要求和匹配分析。
2. 将简历放进数据目录的 `resumes/` 文件夹，填写相对路径，如 `resumes/resume.pdf`。
3. 页面提供本地预览/下载。简历翻译或修改需提前完成，再填入对应版本。
4. 实际提交成功后点击“我已成功投递，登记”，填写日期、使用的简历与成功依据。

批量导入可参考 `examples/catalog.example.json`。导入只添加新岗位，不覆盖已有条目或投递记录。要更新已有岗位资料，可在关闭服务后编辑岗位库JSON，再重启；不要手工修改稳定的 `key`。

## 一周复盘与自动化范围

应用根据投递日期和进度筛选满7个自然日无实质回复的申请。测评、面试、补材料、拒信、录用等均属于实质进展。该筛选不代表企业拒绝了申请。

**本地版不包含自动搜岗位、邮箱连接器、AI匹配分析、简历生成或每日定时通知。** 这些可以由已有外部助手/定时任务完成，并更新本地JSON；本项目负责展示和保存数据。只运行本项目不会自动向企业发送简历。

## 数据与备份

```text
autumn-job-tracker/
  app.py                   # 本地HTTP服务及数据处理
  web/index.html           # 无外部依赖的前端
  start-windows.cmd
  start.sh
  config.example.json
  examples/                # 仅含虚构示例
  tests/
  tools/
  data/                    # 运行时创建，不提交到Git
    岗位库.json
    投递记录.json
    *.backup.json
    resumes/
```

升级时替换程序文件，保留自己的数据目录及 `config.json`。更换电脑时复制数据目录，或使用导出功能。GitHub仓库用于发布程序源代码；不需要GitHub Pages或云服务器。

## 开发与打包

```sh
python -m unittest discover -s tests -v
python tools/build_release.py
```

发布ZIP位于 `dist/autumn-job-tracker-v1.0.0.zip`。打包脚本使用固定程序文件清单，不会带入运行数据、简历、配置或Git历史。

本项目面向单用户本机使用。服务使用Python标准库HTTP实现；[Python官方文档](https://docs.python.org/3/library/http.server.html)不建议将其作为公网生产服务器。若未来需要多人或公网访问，应另行增加认证、HTTPS和生产级服务部署。
