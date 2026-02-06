# SMU-Lecturehelper-GUI
南方医科大学教务抢课脚本

## 来源与声明
- 本项目基于上游仓库二次开发：`https://github.com/rep1ace/SMU-Lecture-Enroller`
- 当前仓库主要新增了 GUI、Cookie 登录流程、四志愿抢课逻辑、自动打包工作流等能力
- 由于包含上游 GPL-2.0 代码与衍生修改，整体按 GPL-2.0 许可发布
- 主体内容由codex创作，缺漏在所难免，抱歉

## CLI 用法
```
pip install uv
uv sync
uv run main.py
```

## GUI 用法（推荐）
```
pip install uv
uv sync
uv run gui.py
```

或直接双击：
- `run_gui.bat`

无 `uv` 时也可直接：
```
py -3 gui.py
```

要求：
- Python 环境必须包含 `tkinter`

### 抢课阶段逻辑
- 前 `PRIMARY_BURST_ATTEMPTS` 次请求只抢第一志愿（当前默认 12 次）
- 之后按志愿顺序轮询抢课
- 支持 4 个志愿：第一/第二必填，第三/第四可留空

### Cookie 登录模式（绕过验证码/统一认证不稳定）
在 GUI 登录区：
- 从浏览器复制 `https://zhjw.smu.edu.cn` 的完整 Cookie 字符串（`name=value; name2=value2; ...`）
- 粘贴到 `Cookie` 输入框
- 点击 `Cookie登录并加载类型`
- 可先点 `打开统一认证/扫码` 在浏览器完成登录，再点 `从剪贴板粘贴Cookie`
- Cookie 输入框默认带 `JSESSIONID=`，也支持只粘贴 JSESSIONID 的值

提示：
- 若提示 `Cookie 会话无效`，先在浏览器重新登录一次教务系统，再复制最新 Cookie

## 无环境一键包（GitHub Actions）
仓库已提供自动打包工作流：`.github/workflows/build-windows.yml`
- 在 GitHub 的 `Actions` 里运行 `Build Windows GUI EXE`
- 构建完成后下载产物 `SMU-Lecture-Enroller-GUI.exe`
- 最终用户可直接运行，不需要本地安装 Python 依赖

## Windows 一键打包 EXE
双击：
- `build_gui.bat`

说明：
- 有 `uv` 时走 `uv` 打包流程
- 无 `uv` 时自动走 `py + pip + pyinstaller` 流程
- 打包环境必须有 `tkinter`（Windows 官方 Python 安装器默认可选组件）

成功后产物在：
- `dist\SMU-Lecture-Enroller-GUI.exe`

## License
- 本项目许可证：`GPL-2.0`（见 `LICENSE`）
