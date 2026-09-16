"""MedSAM 交互式分割平台 - 第一版桌面客户端。

模型未部署时会运行可视化模拟推理；部署后只需替换 ModelGateway 的两个方法。
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, LEFT, RIGHT, X, Y, Canvas, StringVar, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk
# 少数精简 Windows 环境未设置该变量；为 tkdnd 选择正确的 Windows x64 插件。
if os.name == "nt" and not os.environ.get("PROCESSOR_ARCHITECTURE"):
    os.environ["PROCESSOR_ARCHITECTURE"] = "AMD64"

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    WindowBase = TkinterDnD.Tk
    HAS_NATIVE_DND = True
except ImportError:  # 开发环境未安装拖放组件时仍可通过“导入文件”运行。
    import tkinter as tk
    WindowBase = tk.Tk
    HAS_NATIVE_DND = False


APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"
OUTPUT_DIR = Path(r"D:\Download")
SUPPORTED = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


class ModelGateway:
    """统一的模型入口；当前为模拟实现，保留本地与 API 两个替换点。"""

    def run(self, image: Image.Image, box: tuple[int, int, int, int], target: str) -> Image.Image:
        if target == "本地模型":
            return self._local_medsam2(image, box)
        return self._remote_api(image, box)

    def _local_medsam2(self, image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
        # TODO: 模型部署后：在此加载并调用本机/服务器本地 MedSAM2。
        return self._mock_mask(image, box, "本地模型（模拟）")

    def _remote_api(self, image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
        # TODO: API 部署后：将 image 与 box POST 到 config.json 的 remote_api_url。
        return self._mock_mask(image, box, "网络 API（模拟）")

    @staticmethod
    def _mock_mask(image: Image.Image, box: tuple[int, int, int, int], label: str) -> Image.Image:
        base = image.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        x1, y1, x2, y2 = box
        pad_x, pad_y = max(8, (x2 - x1) // 10), max(8, (y2 - y1) // 10)
        region = (max(0, x1 - pad_x), max(0, y1 - pad_y), min(base.width, x2 + pad_x), min(base.height, y2 + pad_y))
        draw.ellipse(region, fill=(34, 197, 94, 95), outline=(16, 185, 129, 255), width=4)
        draw.rectangle((x1, y1, x2, y2), outline=(251, 191, 36, 255), width=3)
        out = Image.alpha_composite(base, overlay).convert("RGB")
        return out


class MedSAMApp(WindowBase):
    def __init__(self) -> None:
        super().__init__()
        self.title("MedSAM 交互式分割平台")
        self.geometry("1450x900")
        self.minsize(1120, 700)
        self.configure(bg="#f5f7fb")
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.result_image: Image.Image | None = None
        self.display_source: ImageTk.PhotoImage | None = None
        self.display_result: ImageTk.PhotoImage | None = None
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)
        self.box_start: tuple[int, int] | None = None
        self.box_id: int | None = None
        self.box_original: tuple[int, int, int, int] | None = None
        self.model_choice = StringVar(value="本地模型")
        self.status = StringVar(value="未加载")
        self.detail = StringVar(value="请拖入影像文件，或点击导入文件。")
        self.gateway = ModelGateway()
        self._build_ui()

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(22, 13))
        header.pack(fill=X)
        ttk.Label(header, text="MedSAM", font=("Microsoft YaHei UI", 20, "bold"), foreground="#0f766e").pack(side=LEFT)
        ttk.Label(header, text="医学影像交互式分割工作平台", font=("Microsoft YaHei UI", 11), foreground="#64748b").pack(side=LEFT, padx=14)
        self.status_badge = ttk.Label(header, textvariable=self.status, font=("Microsoft YaHei UI", 10, "bold"), foreground="#0f766e")
        self.status_badge.pack(side=RIGHT)

        body = ttk.Frame(self, padding=(18, 0, 18, 12))
        body.pack(fill=BOTH, expand=True)
        sidebar = ttk.LabelFrame(body, text="工作台", padding=16, width=220)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 14))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="模型选择", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(5, 6))
        self.model_combo = ttk.Combobox(sidebar, textvariable=self.model_choice, values=["本地模型", "网络 API 模型"], state="readonly")
        self.model_combo.pack(fill=X)
        ttk.Separator(sidebar).pack(fill=X, pady=20)
        ttk.Label(sidebar, text="当前文件", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        self.file_name = ttk.Label(sidebar, text="尚未导入", wraplength=180, foreground="#64748b")
        self.file_name.pack(anchor="w", pady=(8, 20))
        ttk.Button(sidebar, text="📁  导入文件", command=self.choose_file).pack(fill=X, pady=4)
        ttk.Button(sidebar, text="清除当前任务", command=self.clear_task).pack(fill=X, pady=4)
        ttk.Label(sidebar, text="支持 PNG / JPG / BMP / TIFF\nDICOM、NIfTI 将在模型接入时启用。", wraplength=180, foreground="#94a3b8").pack(anchor="w", pady=(24, 0))

        workspace = ttk.Frame(body)
        workspace.pack(side=LEFT, fill=BOTH, expand=True)
        top = ttk.Frame(workspace)
        top.pack(fill=BOTH, expand=True)
        left = ttk.LabelFrame(top, text="待分割影像", padding=8)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 7))
        right = ttk.LabelFrame(top, text="分割结果", padding=8)
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=(7, 0))

        self.source_canvas = Canvas(left, bg="#e9eef5", highlightthickness=0, cursor="crosshair")
        self.source_canvas.pack(fill=BOTH, expand=True)
        self.result_canvas = Canvas(right, bg="#e9eef5", highlightthickness=0)
        self.result_canvas.pack(fill=BOTH, expand=True)
        self.source_canvas.bind("<ButtonPress-1>", self.box_press)
        self.source_canvas.bind("<B1-Motion>", self.box_drag)
        self.source_canvas.bind("<ButtonRelease-1>", self.box_release)
        if HAS_NATIVE_DND:
            self.source_canvas.drop_target_register(DND_FILES)
            self.source_canvas.dnd_bind("<<Drop>>", self.drop_file)
        self.source_canvas.bind("<Configure>", lambda _e: self.render_source())
        self.result_canvas.bind("<Configure>", lambda _e: self.render_result())

        bottom = ttk.Frame(workspace, padding=(0, 14, 0, 0))
        bottom.pack(fill=X)
        message = ttk.Frame(bottom)
        message.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(message, textvariable=self.detail, foreground="#475569").pack(anchor="w")
        ttk.Label(message, text="流程：导入文件 → 在左图拖动绘制框 → 开始执行 → 结果保存至 D:\\Download", foreground="#94a3b8").pack(anchor="w", pady=(4, 0))
        self.run_button = ttk.Button(bottom, text="开始执行", command=self.run_segmentation)
        self.run_button.pack(side=RIGHT, padx=(10, 0))
        self.download_button = ttk.Button(bottom, text="下载结果", command=self.save_result, state="disabled")
        self.download_button.pack(side=RIGHT)

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(title="选择待分割影像", filetypes=[("影像文件", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("所有文件", "*.*")])
        if path:
            self.load_file(Path(path))

    def drop_file(self, event) -> None:
        values = self.tk.splitlist(event.data)
        if values:
            self.load_file(Path(values[0]))

    def load_file(self, path: Path) -> None:
        if not path.exists():
            self.show_error("找不到导入的文件。")
            return
        if path.suffix.lower() not in SUPPORTED:
            self.show_error("当前第一版支持 PNG、JPG、BMP、TIFF 图片。")
            return
        try:
            with Image.open(path) as img:
                self.source_image = ImageOps.exif_transpose(img).convert("RGB").copy()
            self.source_path = path
            self.result_image = None
            self.box_original = None
            self.file_name.configure(text=path.name)
            self.set_state("已加载", "影像已加载。请在左侧图像上拖动鼠标绘制目标框。")
            self.download_button.configure(state="disabled")
            self.render_source()
            self.render_result()
        except Exception as exc:
            self.show_error(f"无法读取该文件：{exc}")

    def _fit(self, image: Image.Image, canvas: Canvas) -> tuple[ImageTk.PhotoImage, float, int, int]:
        canvas.update_idletasks()
        cw, ch = max(canvas.winfo_width(), 100), max(canvas.winfo_height(), 100)
        scale = min((cw - 30) / image.width, (ch - 30) / image.height)
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        preview = image.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(preview), scale, (cw - size[0]) // 2, (ch - size[1]) // 2

    def render_source(self) -> None:
        self.source_canvas.delete("all")
        if not self.source_image:
            self.source_canvas.create_text(240, 180, text="拖放影像至此处\n或点击左侧“导入文件”", fill="#64748b", font=("Microsoft YaHei UI", 14), justify="center")
            return
        self.display_source, self.canvas_scale, ox, oy = self._fit(self.source_image, self.source_canvas)
        self.canvas_offset = (ox, oy)
        self.source_canvas.create_image(ox, oy, image=self.display_source, anchor="nw")
        if self.box_original:
            x1, y1, x2, y2 = self.box_original
            self.box_id = self.source_canvas.create_rectangle(ox + x1 * self.canvas_scale, oy + y1 * self.canvas_scale, ox + x2 * self.canvas_scale, oy + y2 * self.canvas_scale, outline="#f59e0b", width=3)

    def render_result(self) -> None:
        self.result_canvas.delete("all")
        if not self.result_image:
            self.result_canvas.create_text(240, 180, text="分割结果将在这里显示", fill="#94a3b8", font=("Microsoft YaHei UI", 14))
            return
        self.display_result, _scale, ox, oy = self._fit(self.result_image, self.result_canvas)
        self.result_canvas.create_image(ox, oy, image=self.display_result, anchor="nw")

    def box_press(self, event) -> None:
        if not self.source_image:
            self.show_error("请先导入一张影像。")
            return
        self.box_start = (event.x, event.y)
        if self.box_id:
            self.source_canvas.delete(self.box_id)
        self.box_id = self.source_canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#f59e0b", width=3)

    def box_drag(self, event) -> None:
        if self.box_start and self.box_id:
            self.source_canvas.coords(self.box_id, self.box_start[0], self.box_start[1], event.x, event.y)

    def box_release(self, event) -> None:
        if not self.box_start or not self.source_image:
            return
        x1, y1 = self.box_start
        x2, y2 = event.x, event.y
        ox, oy = self.canvas_offset
        values = [int((v - o) / self.canvas_scale) for v, o in ((min(x1, x2), ox), (min(y1, y2), oy), (max(x1, x2), ox), (max(y1, y2), oy))]
        values[0] = max(0, min(values[0], self.source_image.width - 1)); values[2] = max(0, min(values[2], self.source_image.width - 1))
        values[1] = max(0, min(values[1], self.source_image.height - 1)); values[3] = max(0, min(values[3], self.source_image.height - 1))
        if values[2] - values[0] < 5 or values[3] - values[1] < 5:
            self.show_error("框选区域过小，请重新拖动鼠标绘制框。")
        else:
            self.box_original = tuple(values)
            self.set_state("已加载", "目标框已确定。点击“开始执行”进行分割。")
        self.box_start = None

    def run_segmentation(self) -> None:
        if not self.source_image:
            self.show_error("请先导入影像文件。")
            return
        if not self.box_original:
            self.show_error("请先在左侧图像上拖动鼠标画一个目标框。")
            return
        self.run_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self.set_state("推理中", f"正在调用{self.model_choice.get()}，请稍候…")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self) -> None:
        try:
            time.sleep(0.7)  # 模拟真实模型请求耗时
            result = self.gateway.run(self.source_image, self.box_original, self.model_choice.get())
            self.after(0, lambda: self._finish(result))
        except Exception as exc:
            self.after(0, lambda: self.show_error(f"推理失败：{exc}"))

    def _finish(self, result: Image.Image) -> None:
        self.result_image = result
        self.render_result()
        self.run_button.configure(state="normal")
        self.download_button.configure(state="normal")
        self.set_state("完成", "分割完成。可点击“下载结果”保存到 D:\\Download。")

    def save_result(self) -> None:
        if not self.result_image or not self.source_path:
            self.show_error("当前没有可保存的分割结果。")
            return
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = OUTPUT_DIR / f"{self.source_path.stem}_MedSAM_result_{stamp}.png"
            self.result_image.save(destination, "PNG")
            self.set_state("完成", f"结果已保存：{destination}")
            messagebox.showinfo("保存成功", f"结果已保存到：\n{destination}")
        except Exception as exc:
            self.show_error(f"保存结果失败：{exc}")

    def clear_task(self) -> None:
        self.source_path = self.source_image = self.result_image = self.box_original = None
        self.file_name.configure(text="尚未导入")
        self.download_button.configure(state="disabled")
        self.set_state("未加载", "请拖入影像文件，或点击导入文件。")
        self.render_source(); self.render_result()

    def set_state(self, state: str, detail: str) -> None:
        self.status.set(state)
        self.detail.set(detail)

    def show_error(self, detail: str) -> None:
        self.run_button.configure(state="normal")
        self.set_state("失败", detail)
        messagebox.showerror("操作失败", detail)


if __name__ == "__main__":
    MedSAMApp().mainloop()
