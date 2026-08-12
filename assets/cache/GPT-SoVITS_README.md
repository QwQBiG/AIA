# GPT-SoVITS 参考音频设置说明

## 问题说明
系统日志显示：`{"message":"ref_audio_path is required"}`

这表示GPT-SoVITS需要参考音频文件才能正常工作。

## 解决方案

### 方法1：设置参考音频文件
1. 准备一个高质量的音频文件（WAV格式，建议10-30秒）
2. 将音频文件放在 `assets/cache/` 目录下
3. 重命名为 `reference_audio.wav`
4. 重启系统

### 方法2：在GPT-SoVITS WebUI中设置
1. 打开GPT-SoVITS的Web界面（通常是 http://127.0.0.1:9880）
2. 在界面中上传参考音频文件
3. 设置参考文本
4. 保存设置

### 方法3：禁用GPT-SoVITS（使用Edge-TTS）
如果不需要语音克隆功能，可以在GUI中：
1. 打开"基础功能"标签页
2. 取消勾选"GPT-SoVITS 语音克隆"
3. 系统将自动使用Edge-TTS

## 当前配置
- GPT-SoVITS URL: http://127.0.0.1:9880
- 参考音频路径: assets/cache/reference_audio.wav
- 参考文本: "你好，我是娜娜，一个可爱的VTuber！"
- 备用TTS: Edge-TTS (已启用)

## 注意事项
- 参考音频质量直接影响语音克隆效果
- 建议使用清晰、无噪音的音频文件
- 如果GPT-SoVITS服务未运行，系统会自动使用Edge-TTS