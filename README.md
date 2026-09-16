# MedSAM 交互式分割平台（第一版）

运行 `python app.py` 启动开发版。可把 PNG、JPG、BMP 或 TIFF 拖到左侧区域，也可点击“导入文件”选择任意文件；选择支持的图片后，在原图上拖动绘制目标框，再点击“开始执行”。

当前模型尚未部署，程序会使用可视化模拟推理来验证完整操作链路。结果将保存到 `D:\Download`。模型部署后，在 `app.py` 的 `ModelGateway._local_medsam2` 和 `ModelGateway._remote_api` 中分别接入 MedSAM2 本地推理和网络 API。

打包：运行 `build_exe.bat`，生成的可执行文件为 `D:\Download\MedSAM-Platform.exe`。
