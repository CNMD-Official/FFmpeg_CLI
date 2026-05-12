# FFmpeg 多媒体处理工具 （AI-Assisted Development）

一个基于 FFmpeg 的交互式命令行多媒体处理工具，支持格式转换、音频提取和视频/音频剪辑。

## 界面展示
<img width="1734" height="927" alt="image" src="https://github.com/user-attachments/assets/baa6933f-cc7e-4542-a654-0bdaa18162b4" />

## 功能

| 功能 | 说明 | 支持文件类型 |
|------|------|-------------|
| **格式转换** | 在不同多媒体格式之间互转 | 视频 / 音频 / 图片 |
| **提取音频** | 从视频中提取音频 (支持全部或部分提取) | 视频 |
| **视频剪辑** | 剪辑指定时间范围的视频片段 | 视频 |
| **音频剪辑** | 剪辑指定时间范围的音频片段 | 音频 |

## 支持的格式

- **视频**: mp4, mkv, avi, mov, wmv, flv, webm, m4v, ts, 3gp, ogv 等
- **音频**: mp3, aac, wav, flac, ogg, wma, m4a, opus, ac3, aiff 等
- **图片**: jpg, png, bmp, webp, gif, tiff, avif, ico, heic 等

## 技术栈

- **语言**: Python 3 (仅依赖标准库)
- **引擎**: FFmpeg (多媒体编解码与处理)
- **通信**: 通过 `subprocess` 调用 FFmpeg，解析 stdout 实现实时进度

## 环境要求

- Python 3.6+
- FFmpeg（需已安装并添加到系统 PATH，或放在程序同目录下）

### FFmpeg 安装

- **Windows**: 从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载，将 `ffmpeg.exe` 所在目录添加到系统 PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` (Debian/Ubuntu) 或对应包管理器

## 使用方法

```bash
运行FFmpeg_CLI.exe
```

程序启动后，按照交互提示操作：

1. **选取文件** — 输入文件路径（支持拖拽文件到终端）
2. **选择操作** — 根据文件类型自动显示可用的操作
3. **配置参数** — 根据操作类型设置输出格式、时间范围等
4. **执行处理** — 显示实时进度条，处理完成输出文件

### 操作指南

- 在任何输入处输入 `b` / `back` / `返回` 可**返回上一步**
- 在执行 FFmpeg 命令前可选择**添加自定义参数**（如码率、分辨率、编码器等）

## 项目结构

```
FFmpeg_CLI/
├── main.py       # 主程序入(单文件)
└── README.md     # 本文件
```

## 技术实现要点

- **FFmpeg 自动检测**: 优先查找系统 PATH，其次扫描 Windows 常见安装目录，最后检查程序同目录
- **实时进度条**: 通过 `-progress pipe:` 选项读取 FFmpeg 输出流，解析 `out_time` 计算百分比，终端内绘制动态进度条
- **时间解析**: 支持 `HH:MM:SS`、`MM:SS`、纯秒数三种时间输入格式
- **安全输出**: 自动创建输出目录；检测输出路径是否与输入相同以防止覆盖源文件
- **自定义参数**: 执行前允许用户追加任意 FFmpeg 参数，支持 shlex 分割
- **格式建议**: 根据文件类型（视频/音频/图片）推荐常用输出格式
