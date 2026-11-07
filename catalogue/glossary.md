# MOTO-HUB 简体中文翻译规范（所有翻译者必须遵守）

## 0. 应用背景
MOTO-HUB 是一个摩托车 Android 车载（Car App）应用：把手机的 Android Auto 界面**投屏**到摩托车仪表盘（TFT）上，并提供骑行仪表盘、导航、行程记录/回放、OBD 诊断读数、车队语音对讲、语音笔记、照片/影片记录、AI 地点推荐等功能。手机通过 T-Box（车机盒子）与摩托车连接。

## 1. 不翻译的东西（原样保留）
- 品牌与技术专名：`MOTO-HUB`、`ADV-SOLO`、`Android Auto`、`T-Box`、`TFT`、`OBD`、`GPS`、`Wi-Fi`、`Bluetooth`（但行文里 Bluetooth 作名词译「蓝牙」）、`MapLibre`、`Torque`、`HeGPS`、`CFDL`、`KTM`、`DUCATI`、`Honda`、`BMW`、`GPS`、`SSID`、`BSSID`、`IMEI`、`IP`、`QR`、`API`、`URL`、`AI`、`m/s`、`km/h`、`mph`、`°C`、`°`、`%`、`rpm`、`Hz`、`ms`、`GB`、`MB`、`Wi-Fi 频段`、`2.4 GHz`、`5 GHz`。
- 单位与符号：`km`、`m`、`h`、`L`、`km/L`、`°`、`%`、`%%`。
- 车辆配置代码（如 `CFDL16 / Legacy`）保持原样，仅翻译其后的说明文字。
- 韩文/俄文/拉丁带重音字母的品牌或人名样例若属于专有名词（如 `Škoda`）保持原样。
- 符号字符：`·`、`—`、`…`、`→`、`‹`、`›`、`▼`、`▲`、`◂`、`▶`、`◀`、`▸`、`✓`、`↔`、`↗`、`↘`、`±`、`×`、`Δ`、`☆`、`💧`、`⛰`、`✨`、`⣿` —— 保留原符号，只翻译周围的文字。

## 2. 核心术语表（必须严格一致）
| English | 中文 |
|---|---|
| dashboard（摩托车仪表本身） | 仪表盘 |
| Ride Dashboard（功能名） | 骑行仪表盘 |
| handlebar / handlebars | 车把 |
| handlebar buttons | 车把按键 |
| glove / gloves | 手套 |
| T-Box | T-Box |
| projection / project / projected | 投屏 |
| pairing / pair / paired / unpaired | 配对 / 已配对 / 未配对 |
| ride / riding | 骑行 |
| trip（一次行程） | 行程 |
| route | 路线 |
| waypoint | 途经点 |
| stop（作为导航停靠点，"Add as stop"） | 途经点 |
| stop（作为动作"停止"） | 停止 |
| navigation / navigate | 导航 / 导航至 |
| reroute / re-route | 重新规划路线 |
| search | 搜索 |
| map | 地图 |
| speed | 速度 |
| speed limit | 限速 |
| throttle | 油门 |
| brake | 刹车 |
| lean angle | 倾角 |
| RPM | 转速 |
| fuel / fuel level | 油量 |
| coolant | 水温 |
| engine | 发动机 |
| OBD adapter | OBD 适配器 |
| adapter | 适配器 |
| intercom | 对讲 |
| group voice（车队语音） | 车队语音 |
| audio note | 语音笔记 |
| photo | 照片 |
| film / footage | 影片 / 影像 |
| clip | 片段 |
| replay | 回放 |
| recording | 录制 |
| calibration | 校准 |
| profile（车辆配置档） | 配置 |
| settings | 设置 |
| remote / remote control | 遥控器 / 遥控 |
| button | 按键 |
| screen | 屏幕 |
| brightness | 亮度 |
| resolution | 分辨率 |
| density / dpi | 密度 / dpi |
| safe margins | 安全边距 |
| portrait | 竖屏 |
| landscape | 横屏 |
| orientation | 方向 |
| hotspot | 热点 |
| network | 网络 |
| connection / connected / disconnected | 连接 / 已连接 / 已断开 |
| session | 会话 |
| log | 日志 |
| version | 版本 |
| update | 更新 |
| permission | 权限 |
| notification | 通知 |
| voice | 语音 |
| assistant | 助手 |
| weather: RAIN / PARTLY CLOUDY / CLEAR | 降雨 / 多云 / 晴 |
| riding mode: Sport / Street / Rain | 运动 / 街道 / 雨天 |
| phone | 手机 |
| car / head unit | 车机 |
| video / audio | 视频 / 音频 |
| microphone | 麦克风 |
| GPS signal / satellite | GPS 信号 / 卫星 |
| fuel gauge | 油量表 |
| trip metrics | 行程数据 |
| average / max / min | 平均 / 最大 / 最小 |

## 3. 风格要求
1. **UI 语气**：面向普通车主的简洁说明文，短句，去掉英文里多余的客套（"You do not need to install anything." → "无需安装任何东西。"）。
2. **长度**：小 TFT 仪表盘上的极短标签（AUDIO NOTES、BUTTONS TAUGHT、AVERAGE MPH、RAIN 这类，全大写且 ≤ 4 个英文单词）必须译得**同样短**，≤ 8 个汉字；必要时保留单位。
3. 全大写的英文标签译成中文时**不要**再加全大写或空格填充，直接写中文即可。
4. **句子末尾不加句号**：UI 按钮、标题、菜单项、标签一律不加标点；完整的说明句和提示句才加句号。
5. 不要翻译成书面官腔，不要用「您」以外的敬语堆砌；用「你」。
6. 不要凭空添加原文没有的信息，不要漏译原文里的限定语（如 "only"、"first"、"on this phone"）。
7. 半角标点用中文全角（，。：；？），但 `%1$s`、`%d`、`%%` 等占位符前后不要加空格以外的多余字符。

## 4. 占位符（绝对红线）
- `%1$s`、`%2$d`、`%1$.1f` 等占位符必须**逐字保留**，个数、顺序、类型都不能变。
- `%%` 表示字面量百分号，必须保留为 `%%`。
- 占位符不要翻译，也不要改成中文语序后重新编号；中文语序要调整时，请把占位符整体搬到合适位置，但编号不变。例如 `"%1$s and %2$s"` → `"%1$s 和 %2$s"`。
- 占位符前后也不要加中文引号等会改变含义的符号。

## 5. 输出格式
返回**严格的 JSON 数组**，每个元素 `{"name": "资源名", "zh": "中文译文"}`，与输入顺序一一对应，一个都不能少、不能多。
- `zh` 里只放纯文本，**不要**写 XML 转义（`&` `<` `>` 保持原字符即可），不要加 `\n` 字面量（真的换行就写真换行符），不要加任何解释文字。
- 不要把资源名当成待翻译内容；只翻译 `en` 字段。
- 如果某条确实是品牌名、代码、纯符号（例如 `MOTO-HUB`、`androidx.startup`、`Wi-Fi`），照抄原文即可。