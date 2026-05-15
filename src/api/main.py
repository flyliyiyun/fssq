"""
FSSQ 风生水起 — FastAPI Web 服务
Phase 2 Web 服务化入口

启动命令：
    uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload

或直接运行：
    python3 src/api/main.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# 路径修正：确保能导入 src 下的模块
_ROOT = Path(__file__).resolve().parent.parent.parent   # /玄学合集/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 城市经纬度预置表
CITY_COORDS: dict[str, tuple[float, float]] = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969),
    "重庆": (29.5630, 106.5516),
    "厦门": (24.4798, 118.0894),
    "福州": (26.0745, 119.2965),
    "郑州": (34.7466, 113.6253),
    "开封": (34.7970, 114.3070),
    "洛阳": (34.6197, 112.4540),
    "苏州": (31.2990, 120.5853),
    "天津": (39.3434, 117.3616),
    "沈阳": (41.8057, 123.4315),
    "哈尔滨": (45.7580, 126.6428),
    "长沙": (28.2282, 112.9388),
    "合肥": (31.8206, 117.2272),
    "南昌": (28.6820, 115.8579),
    "石家庄": (38.0428, 114.5149),
    "太原": (37.8706, 112.5489),
    "济南": (36.6512, 117.1201),
    "青岛": (36.0671, 120.3826),
    "大连": (38.9140, 121.6147),
    "宁波": (29.8683, 121.5440),
    "佛山": (23.0222, 113.1216),
    "东莞": (23.0207, 113.7518),
    "昆明": (25.0389, 102.7183),
    "贵阳": (26.5983, 106.7072),
    "南宁": (22.8170, 108.3665),
    "海口": (20.0447, 110.3312),
    "乌鲁木齐": (43.8256, 87.6168),
    "兰州": (36.0611, 103.8343),
    "西宁": (36.6232, 101.7782),
    "银川": (38.4681, 106.2733),
    "呼和浩特": (40.8428, 111.7499),
    "长春": (43.8171, 125.3235),
    "旧金山": (37.7749, -122.4194),
    "纽约": (40.7128, -74.0060),
    "洛杉矶": (34.0522, -118.2437),
    "伦敦": (51.5074, -0.1278),
    "东京": (35.6762, 139.6503),
    "新加坡": (1.3521, 103.8198),
    "香港": (22.3193, 114.1694),
    "台北": (25.0330, 121.5654),
    "首尔": (37.5665, 126.9780),
    "悉尼": (-33.8688, 151.2093),
}


def _get_coords(place: str) -> tuple[float, float]:
    """城市名→经纬度，优先精确匹配，其次模糊匹配"""
    if place in CITY_COORDS:
        return CITY_COORDS[place]
    for k, v in CITY_COORDS.items():
        if place in k or k in place:
            return v
    return (34.7970, 114.3070)  # 默认开封


# ── Pydantic 模型 ─────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    birth_date: str = Field(..., description="出生日期，格式 YYYY-MM-DD", example="1974-07-05")
    birth_hour: int = Field(..., ge=0, le=23, description="出生时辰 0-23", example=17)
    gender: str = Field(..., description="性别：男/女", example="男")
    birth_place: str = Field("开封", description="出生地城市名", example="开封")
    target_year: int = Field(default_factory=lambda: datetime.now().year, description="目标年份", example=2026)
    current_place: Optional[str] = Field(None, description="现居住地", example="旧金山")
    birth_lat: Optional[float] = Field(None, description="出生地纬度（可选，优先于城市名）")
    birth_lon: Optional[float] = Field(None, description="出生地经度（可选，优先于城市名）")
    dayun_mode: str = Field("day_gan", description="大运排法：day_gan（日干派）/ year_gan（年干派）")
    snipe_enabled: bool = Field(True, description="是否启用 SnipeScore 评分")


class ReportStatus(BaseModel):
    report_id: str
    status: str           # pending / running / done / error
    message: str
    created_at: str
    html_url: Optional[str] = None
    json_url: Optional[str] = None
    summary: Optional[dict] = None


# ── 内存中的任务注册表（生产环境应换成 Redis / DB） ─────────────────────────
_tasks: dict[str, dict] = {}


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="FSSQ 风生水起 — 玄学选股引擎",
    description=(
        "精度优先的玄学+量化辅助决策工具。\n\n"
        "核心逻辑：个人命盘（八字40%+紫微30%+奇门20%+占星10%）× 大势环境 → A股板块推荐 + SnipeScore 8维量化评分\n\n"
        "**使用流程**：\n"
        "1. `POST /report` 提交生辰信息，返回 `report_id`\n"
        "2. `GET /report/{report_id}` 轮询状态，`status=done` 时获取 HTML 报告链接\n"
        "3. `GET /report/{report_id}/html` 直接获取 HTML 报告"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（允许小程序/本地调试访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务：报告 HTML/JSON
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


# ── 后台任务：运行 Pipeline ───────────────────────────────────────────────────

async def _run_pipeline_bg(report_id: str, req: ReportRequest):
    """在事件循环外线程中运行同步 pipeline"""
    _tasks[report_id]["status"] = "running"
    _tasks[report_id]["message"] = "Pipeline 运行中，请稍候..."

    try:
        # 解析经纬度
        if req.birth_lat and req.birth_lon:
            lat, lon = req.birth_lat, req.birth_lon
        else:
            lat, lon = _get_coords(req.birth_place)

        # 构造 pipeline 参数 dict
        config = {
            "birth_date": req.birth_date,
            "birth_hour": req.birth_hour,
            "gender": req.gender,
            "birth_place": req.birth_place,
            "birth_lat": lat,
            "birth_lon": lon,
            "target_year": req.target_year,
            "current_place": req.current_place or "",
            "dayun_mode": req.dayun_mode,
            "output_dir": str(OUTPUT_DIR),
            "report_id": report_id,   # 可供 orchestrator 使用自定义文件名
        }

        # 用子进程隔离运行（避免占用 event loop）
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(_ROOT / "run_pipeline.py"),
            "--birth",    req.birth_date,
            "--hour",     str(req.birth_hour),
            "--gender",   req.gender,
            "--place",    req.birth_place,
            "--year",     str(req.target_year),
            "--current",  req.current_place or "",
            "--lat",      str(lat),
            "--lon",      str(lon),
            "--dayun_mode", req.dayun_mode,
            "--snipe",    "1" if req.snipe_enabled else "0",
            "--output",   str(OUTPUT_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_ROOT),
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            raise RuntimeError(f"Pipeline 退出码 {proc.returncode}\n{output[-2000:]}")

        # 查找生成的 HTML 文件（按时间取最新）
        date_str = req.birth_date.replace("-", "")
        html_pattern = f"FSSQ_{date_str}_{req.gender}_{req.target_year}.html"
        html_path = OUTPUT_DIR / html_pattern
        json_path = OUTPUT_DIR / html_pattern.replace(".html", "_result.json")

        if not html_path.exists():
            # 找最新的同日期报告
            candidates = sorted(OUTPUT_DIR.glob(f"FSSQ_{date_str}_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                html_path = candidates[0]
                json_path = html_path.with_name(html_path.stem + "_result.json")

        if not html_path.exists():
            raise FileNotFoundError("Pipeline 完成但找不到 HTML 报告文件")

        # 读取摘要
        summary = {}
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                raw = json.load(f)
            s = raw.get("summary", {})
            summary = {
                "bazi": s.get("bazi", ""),
                "yong_shen": s.get("yong_shen", ""),
                "top_sectors": s.get("top_sectors", []),
                "top_stocks": s.get("top_stocks", []),
            }

        _tasks[report_id].update({
            "status": "done",
            "message": "报告生成成功",
            "html_filename": html_path.name,
            "json_filename": json_path.name if json_path.exists() else None,
            "summary": summary,
            "html_url": f"/output/{html_path.name}",
            "json_url": f"/output/{json_path.name}" if json_path.exists() else None,
        })
        logger.info(f"[{report_id}] Pipeline 完成 → {html_path.name}")

    except Exception as exc:
        logger.exception(f"[{report_id}] Pipeline 失败")
        _tasks[report_id].update({
            "status": "error",
            "message": str(exc)[:500],
        })


# ── 路由 ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, summary="服务首页")
async def home():
    """返回国潮风水风格H5前端"""
    html_path = _ROOT / "src" / "frontend" / "index.html"
    if html_path.exists():
        with open(html_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    
    # 回退：返回内嵌HTML
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FSSQ 风生水起</title>
<style>
  body { font-family: -apple-system, 'PingFang SC', sans-serif;
         max-width: 720px; margin: 60px auto; padding: 0 20px;
         background: #0d1117; color: #c9d1d9; }
  h1 { font-size: 28px; color: #ffd700; }
  /* ... 内嵌表单样式 ... */
</style>
</head>
<body>
<h1>📊 FSSQ 风生水起</h1>
<p>服务运行中，请访问 <a href="/docs">API文档</a></p>
</body></html>"""
    return HTMLResponse(content=html)


@app.post("/report", response_model=ReportStatus, summary="提交命盘报告生成请求")
async def create_report(req: ReportRequest, background_tasks: BackgroundTasks):
    """
    提交生辰信息，异步触发 4-Agent Pipeline 生成报告。

    - 立即返回 `report_id`，无需等待
    - 通过 `GET /report/{report_id}` 轮询状态
    - `status` 取值：`pending` → `running` → `done` / `error`
    """
    report_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat(timespec="seconds")

    _tasks[report_id] = {
        "report_id": report_id,
        "status": "pending",
        "message": "已排队，等待启动",
        "created_at": now,
        "html_url": None,
        "json_url": None,
        "summary": None,
        "html_filename": None,
        "json_filename": None,
    }

    background_tasks.add_task(_run_pipeline_bg, report_id, req)

    logger.info(f"[{report_id}] 新报告请求 birth={req.birth_date} gender={req.gender} year={req.target_year}")
    return ReportStatus(
        report_id=report_id,
        status="pending",
        message="已排队，等待启动",
        created_at=now,
    )


@app.get("/report/{report_id}", response_model=ReportStatus, summary="查询报告状态")
async def get_report_status(report_id: str):
    """
    轮询报告生成状态。

    - `status=pending/running`：仍在生成中，请继续轮询
    - `status=done`：生成成功，`html_url` 可访问
    - `status=error`：生成失败，`message` 含错误信息
    """
    task = _tasks.get(report_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"report_id {report_id!r} 不存在")

    return ReportStatus(
        report_id=task["report_id"],
        status=task["status"],
        message=task["message"],
        created_at=task["created_at"],
        html_url=task.get("html_url"),
        json_url=task.get("json_url"),
        summary=task.get("summary"),
    )


@app.get("/report/{report_id}/html", response_class=HTMLResponse, summary="直接获取 HTML 报告")
async def get_report_html(report_id: str):
    """直接返回 HTML 报告内容（报告完成后可用）"""
    task = _tasks.get(report_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"report_id {report_id!r} 不存在")
    if task["status"] != "done":
        raise HTTPException(status_code=425, detail=f"报告尚未生成完毕，当前状态: {task['status']}")

    html_path = OUTPUT_DIR / task["html_filename"]
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="HTML 文件不存在")

    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/report/{report_id}/json", summary="直接获取 JSON 数据")
async def get_report_json(report_id: str):
    """直接返回完整 JSON 数据（报告完成后可用）"""
    task = _tasks.get(report_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"report_id {report_id!r} 不存在")
    if task["status"] != "done":
        raise HTTPException(status_code=425, detail=f"报告尚未生成完毕，当前状态: {task['status']}")

    json_fn = task.get("json_filename")
    if not json_fn:
        raise HTTPException(status_code=404, detail="JSON 文件不存在")

    json_path = OUTPUT_DIR / json_fn
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="JSON 文件不存在")

    with open(json_path, encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.get("/reports", summary="列出所有已生成报告")
async def list_reports():
    """列出当前会话中所有报告的状态（按创建时间倒序）"""
    tasks_sorted = sorted(
        _tasks.values(),
        key=lambda t: t.get("created_at", ""),
        reverse=True,
    )
    return {
        "total": len(tasks_sorted),
        "reports": [
            {
                "report_id": t["report_id"],
                "status": t["status"],
                "message": t["message"],
                "created_at": t["created_at"],
                "html_url": t.get("html_url"),
            }
            for t in tasks_sorted
        ],
    }


@app.get("/health", summary="健康检查")
async def health():
    """服务健康检查"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "output_dir": str(OUTPUT_DIR),
        "report_count": len(_tasks),
        "timestamp": datetime.now().isoformat(),
    }


# ── 开发模式直接运行 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("FSSQ 风生水起 Web 服务")
    print("地址：http://0.0.0.0:8080")
    print("文档：http://localhost:8080/docs")
    print("首页：http://localhost:8080/")
    print("=" * 60)
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=[str(_ROOT / "src")],
        app_dir=str(_ROOT),
    )
