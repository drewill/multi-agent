# README 截图替换说明

## 文件怎么放

此目录中的 banner.svg 是原创项目横幅，可以直接保留。
home-placeholder.svg、workspace-placeholder.svg、report-placeholder.svg 是明确标注的占位图，不是项目截图。

请在浏览器打开你的项目，使用 Win + Shift + S 截取真实页面，保存为：

- home.png：首页，包含产品标题与两个入口。
- workspace.png：左侧有一段对话，右侧有真实计划，最好包含更新提示。
- report.png：面试报告，包含逐题反馈、薄弱点和两个操作按钮。

推荐用PNG，浏览器缩放100%，桌面截图宽度约1440～1920像素。不要截入密钥、个人隐私或无关浏览器标签。

## 修改README的三行

把：
```markdown
![首页截图待补充](docs/images/home-placeholder.svg)
![聊天与计划预览截图待补充](docs/images/workspace-placeholder.svg)
![面试报告截图待补充](docs/images/report-placeholder.svg)
```

改为：
```markdown
![首页](docs/images/home.png)
![流式聊天与计划预览](docs/images/workspace.png)
![模拟面试报告](docs/images/report.png)
```

替换完后删除README“界面预览”下面关于占位图的提示，并可删除本目录三个placeholder.svg。没有某张截图时可以先删去对应小节，不要留下不存在的图片路径。

## 如何提交

把本包的README.md放到项目根目录，docs文件夹也放到项目根目录：
```powershell
git add README.md docs
git diff --cached --stat
git commit -m "docs: refresh README and add project screenshots"
git push
```

只替换文档与图片，不要覆盖项目代码、.env或数据库。本包没有自动提交或推送任何文件。
