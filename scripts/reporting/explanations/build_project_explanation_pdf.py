"""本文件生成项目原理说明PDF，集中展示运行流程、匹配方法、角色输出与验收结果。"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#172B4D")
BURGUNDY = colors.HexColor("#9B2438")
GOLD = colors.HexColor("#D8A23A")
INK = colors.HexColor("#243447")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D9E2EC")
PALE = colors.HexColor("#F4F7FA")
GREEN = colors.HexColor("#2E7D62")
ORANGE = colors.HexColor("#C66A20")
WHITE = colors.white


def register_fonts() -> tuple[str, str]:
    """注册可显示中文的字体；非Windows环境自动回退到常见CJK字体。"""
    candidates = [
        ("MicrosoftYaHei", Path("C:/Windows/Fonts/msyh.ttc")),
        ("NotoSansCJK", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
        ("PingFang", Path("/System/Library/Fonts/PingFang.ttc")),
    ]
    bold_candidates = [
        ("MicrosoftYaHeiBold", Path("C:/Windows/Fonts/msyhbd.ttc")),
        ("NotoSansCJKBold", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")),
        ("PingFangBold", Path("/System/Library/Fonts/PingFang.ttc")),
    ]
    regular_name = "Helvetica"
    bold_name = "Helvetica-Bold"
    for name, path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            regular_name = name
            break
    for name, path in bold_candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            bold_name = name
            break
    return regular_name, bold_name


class PipelineDiagram(Flowable):
    """绘制从原始输入到角色报告的安全匹配流程。"""

    def __init__(self, font_name: str, width: float = 174 * mm, height: float = 53 * mm):
        super().__init__()
        self.font_name = font_name
        self.width = width
        self.height = height

    def draw(self):
        canvas = self.canv
        labels = ["原始资料", "风险审计", "评分副本", "80项评分", "角色报告"]
        notes = ["简历 / JD", "敏感项与注入", "脱敏且保留业务信息", "硬门槛 + 双向加权", "HR / 求职者 / 面试官 / 人才发展"]
        box_width = 31 * mm
        gap = 4.5 * mm
        y = 18 * mm
        for index, (label, note) in enumerate(zip(labels, notes)):
            x = index * (box_width + gap)
            fill = BURGUNDY if index in {1, 3} else NAVY
            canvas.setFillColor(fill)
            canvas.roundRect(x, y, box_width, 18 * mm, 3 * mm, fill=1, stroke=0)
            canvas.setFillColor(WHITE)
            canvas.setFont(self.font_name, 9)
            canvas.drawCentredString(x + box_width / 2, y + 10.8 * mm, label)
            canvas.setFillColor(MUTED)
            canvas.setFont(self.font_name, 6.6)
            canvas.drawCentredString(x + box_width / 2, y - 4.5 * mm, note)
            if index < len(labels) - 1:
                arrow_x = x + box_width + 1.1 * mm
                canvas.setStrokeColor(GOLD)
                canvas.setFillColor(GOLD)
                canvas.setLineWidth(1.6)
                canvas.line(arrow_x, y + 9 * mm, arrow_x + 2.8 * mm, y + 9 * mm)
                canvas.line(arrow_x + 2.8 * mm, y + 9 * mm, arrow_x + 1.7 * mm, y + 10.1 * mm)
                canvas.line(arrow_x + 2.8 * mm, y + 9 * mm, arrow_x + 1.7 * mm, y + 7.9 * mm)


class ScoreBars(Flowable):
    """绘制企业侧、求职者侧与证据置信度的示意条形图。"""

    def __init__(self, font_name: str, width: float = 170 * mm, height: float = 50 * mm):
        super().__init__()
        self.font_name = font_name
        self.width = width
        self.height = height

    def draw(self):
        canvas = self.canv
        rows = [("企业侧适配", 87.59, BURGUNDY), ("求职者侧适配", 92.40, NAVY), ("结果置信度", 90.57, GOLD)]
        bar_x = 41 * mm
        bar_width = 112 * mm
        for index, (label, value, color) in enumerate(rows):
            y = self.height - (index + 1) * 14 * mm
            canvas.setFont(self.font_name, 9)
            canvas.setFillColor(INK)
            canvas.drawString(0, y + 2.2 * mm, label)
            canvas.setFillColor(LINE)
            canvas.roundRect(bar_x, y, bar_width, 6 * mm, 3 * mm, fill=1, stroke=0)
            canvas.setFillColor(color)
            canvas.roundRect(bar_x, y, bar_width * value / 100, 6 * mm, 3 * mm, fill=1, stroke=0)
            canvas.setFillColor(INK)
            canvas.drawRightString(self.width, y + 2.2 * mm, f"{value:.2f}")


class MetricSplit(Flowable):
    """绘制80项指标在双向评分中的数量分布。"""

    def __init__(self, font_name: str, width: float = 170 * mm, height: float = 42 * mm):
        super().__init__()
        self.font_name = font_name
        self.width = width
        self.height = height

    def draw(self):
        canvas = self.canv
        total_width = 164 * mm
        left_width = total_width * 42 / 80
        y = 19 * mm
        canvas.setFillColor(BURGUNDY)
        canvas.roundRect(0, y, left_width, 13 * mm, 4 * mm, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.roundRect(left_width - 4 * mm, y, total_width - left_width + 4 * mm, 13 * mm, 4 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont(self.font_name, 10)
        canvas.drawCentredString(left_width / 2, y + 5.2 * mm, "企业侧 42项")
        canvas.drawCentredString(left_width + (total_width - left_width) / 2, y + 5.2 * mm, "求职者侧 38项")
        canvas.setFillColor(MUTED)
        canvas.setFont(self.font_name, 8)
        canvas.drawString(0, y - 8 * mm, "所有影响系数均从Excel实时读取，范围0-10；岗位模板可覆盖基础系数。")


def make_styles(font_name: str, bold_name: str):
    """创建全篇统一的中文排版样式。"""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCN", parent=base["Title"], fontName=bold_name, fontSize=28,
            leading=36, textColor=NAVY, alignment=TA_LEFT, spaceAfter=10 * mm,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCN", parent=base["Normal"], fontName=font_name, fontSize=12,
            leading=20, textColor=MUTED, spaceAfter=7 * mm,
        ),
        "h1": ParagraphStyle(
            "H1CN", parent=base["Heading1"], fontName=bold_name, fontSize=20,
            leading=28, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "H2CN", parent=base["Heading2"], fontName=bold_name, fontSize=12,
            leading=18, textColor=BURGUNDY, spaceBefore=3 * mm, spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCN", parent=base["BodyText"], fontName=font_name, fontSize=9.2,
            leading=15, textColor=INK, spaceAfter=2.5 * mm,
        ),
        "small": ParagraphStyle(
            "SmallCN", parent=base["BodyText"], fontName=font_name, fontSize=7.8,
            leading=12, textColor=MUTED,
        ),
        "callout": ParagraphStyle(
            "CalloutCN", parent=base["BodyText"], fontName=bold_name, fontSize=10.2,
            leading=16, textColor=BURGUNDY, backColor=colors.HexColor("#FCEFF1"),
            borderPadding=8, borderColor=colors.HexColor("#F0C9D0"), borderWidth=0.8,
            borderRadius=4, spaceBefore=3 * mm, spaceAfter=4 * mm,
        ),
        "center": ParagraphStyle(
            "CenterCN", parent=base["BodyText"], fontName=font_name, fontSize=8.5,
            leading=13, textColor=INK, alignment=TA_CENTER,
        ),
        "header_center": ParagraphStyle(
            "HeaderCenterCN", parent=base["BodyText"], fontName=bold_name, fontSize=8.2,
            leading=12, textColor=WHITE, alignment=TA_CENTER,
        ),
    }


def p(text: str, style) -> Paragraph:
    """把普通文本包装成可在表格和正文中复用的段落。"""
    return Paragraph(text, style)


def styled_table(data, widths, styles, header=True, font_name="Helvetica", bold_name="Helvetica-Bold"):
    """生成统一的圆角感表格，表头与正文使用中文字体。"""
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, PALE]),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), bold_name),
        ])
    table.setStyle(TableStyle(commands))
    return table


def header_footer(canvas, doc, font_name: str, bold_name: str):
    """绘制除封面外的页眉、页脚和页码。"""
    canvas.saveState()
    page = canvas.getPageNumber()
    width, height = A4
    if page > 1:
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
        canvas.setFont(bold_name, 8)
        canvas.setFillColor(NAVY)
        canvas.drawString(18 * mm, height - 10.5 * mm, "TalentLens 双向人才与机会匹配")
        canvas.setFont(font_name, 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - 18 * mm, height - 10.5 * mm, "项目解释说明")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont(font_name, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8.5 * mm, "可复现基准日：2026-07-15 | 人工复核后决策")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"第 {page} 页")
    canvas.restoreState()


def build_story(styles, font_name: str, bold_name: str):
    """组织十页项目说明内容。"""
    story = []

    story.extend([
        Spacer(1, 24 * mm),
        p("TalentLens", styles["title"]),
        p("双向人才与机会匹配 Skill", styles["h1"]),
        p("项目原理、运行流程、匹配方法与多平台调用说明", styles["subtitle"]),
        Spacer(1, 8 * mm),
        PipelineDiagram(font_name),
        Spacer(1, 14 * mm),
        p("它不只回答“这个人能不能胜任”，也回答“这个机会是否适合这个人”。系统把简历、岗位要求和个人偏好转成可核对的数据，先审计风险，再用脱敏副本计算80项指标；资料不足或硬条件未核验时，不展示容易误导的正式分。", styles["callout"]),
        Spacer(1, 15 * mm),
        styled_table([
            [p("版本", styles["header_center"]), p("指标", styles["header_center"]), p("角色报告", styles["header_center"]), p("自动测试", styles["header_center"])],
            [p("4.2.0", styles["center"]), p("80项", styles["center"]), p("4类", styles["center"]), p("122项", styles["center"])],
        ], [38 * mm, 38 * mm, 48 * mm, 38 * mm], styles, font_name=font_name, bold_name=bold_name),
        PageBreak(),
    ])

    story.extend([
        p("01 项目解决什么问题", styles["h1"]),
        p("人才匹配最容易出错的地方，不是缺少一个分数，而是信息不完整、硬条件边界模糊、招聘方和求职者目标不对称。TalentLens把判断拆成证据、规则、分数和人工决策四层。", styles["body"]),
        styled_table([
            ["使用者", "最关心的内容", "报告侧重点", "决策边界"],
            ["HR / 招聘", "候选人是否满足岗位要求", "硬条件、关键证据、风险、补证顺序、候选人顾虑", "系统不给录用或淘汰结论"],
            ["求职者", "岗位是否符合个人目标", "薪资地点、成长空间、差距、面试准备", "未知信息不会被写成个人缺点"],
            ["面试官", "如何公平验证关键能力", "统一问题、评分锚点、追问和记录栏", "避免询问受保护个人信息"],
            ["人才发展", "离目标岗位还差什么", "准备度、迁移技能、证据缺口、30/60/90天计划", "用于发展对话，不做自动人事决定"],
        ], [25 * mm, 42 * mm, 68 * mm, 39 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 6 * mm),
        p("三个设计原则", styles["h2"]),
        styled_table([
            ["可追溯", "可配置", "不误导"],
            ["每个分数关联来源字段、证据片段和系数", "80项系数与岗位模板从Excel读取", "未知不当作0；硬条件未知不显示正式分"],
        ], [58 * mm] * 3, styles, font_name=font_name, bold_name=bold_name),
        PageBreak(),
    ])

    story.extend([
        p("02 运行流程", styles["h1"]),
        p("从输入到报告共经过八步。外部大模型可以协助把自然语言转成结构化JSON，但核心校验、门槛、评分和审计由本地确定性代码完成。", styles["body"]),
        PipelineDiagram(font_name),
        styled_table([
            ["步骤", "系统动作", "产生的结果"],
            ["1. 接收", "读取JSON、TXT、Markdown、CSV、JSONL或DOCX", "原始候选人和岗位资料"],
            ["2. 审计", "在原始资料上识别敏感条件、个人信息和提示注入", "风险标记与排除路径"],
            ["3. 清洗", "生成仅用于评分的脱敏副本", "敏感属性不会进入分数"],
            ["4. 解析", "提取中文数字年限、跨行列表、薪资、日期和AND/OR要求", "带来源状态与歧义标记的结构化字段"],
            ["5. 门槛", "先判断硬条件满足、失败或待核验", p("hard_failure /<br/>hard_requirement_unverified", styles["small"])],
            ["6. 评分", "从Excel加载80项系数并计算企业侧与求职者侧", "分项分、暂估分、置信度"],
            ["7. 补证", "针对高权重未知项生成类型化问题", "补证清单与重评变化"],
            ["8. 输出", "按角色生成JSON、Markdown、HTML和SVG", "不同读者看到不同重点"],
        ], [17 * mm, 96 * mm, 61 * mm], styles, font_name=font_name, bold_name=bold_name),
        PageBreak(),
    ])

    story.extend([
        p("03 公平性、隐私与资料来源", styles["h1"]),
        p("公平性不是在分数算完后补一条警告，而是在计算前建立隔离边界。系统先保留原始输入用于审计，再移除年龄、性别、婚育、户籍、健康等字段及相关文本，只把业务相关副本交给评分器。", styles["callout"]),
        styled_table([
            ["数据状态", "含义", "评分处理"],
            ["provided", "用户明确提供了字段和值", "校验通过后参与评分"],
            ["explicit_empty", "用户明确确认该项为空", "可以判断为缺口"],
            ["omitted", "输入中没有这个字段", "记为unknown，不当作0"],
            ["inferred", "解析器从文本推断", "保留来源，允许人工核对"],
            ["extraction_failed", "文本可能有信息但解析失败", "保持unknown并请求补证"],
        ], [34 * mm, 76 * mm, 64 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 5 * mm),
        p("公平性不变性验证", styles["h2"]),
        ScoreBars(font_name),
        p("把“限男性、30岁以下”等条件加入岗位文本后，风险审计会报警，但评分副本会删除这些内容。固定输入下，加入前后暂估总分差为0.00。证据复核和补证重评也只返回脱敏预览与变更字段路径，不回显姓名、手机号和邮箱。", styles["body"]),
        PageBreak(),
    ])

    story.extend([
        p("04 80项指标与Excel配置", styles["h1"]),
        p("指标不是写死在提示词里。reference_indicators目录中的Excel工作簿是判断标准的唯一配置入口，第一列为0-10影响系数；每次匹配都会重新读取，修改后无需改代码。", styles["body"]),
        MetricSplit(font_name),
        styled_table([
            ["指标大类", "示例", "证据不足时"],
            ["技能能力", "必备技能覆盖、熟练度、核心深度、技能新鲜度", "保持unknown，要求补充项目或作品证据"],
            ["岗位履历", "相关经验、行业经验、职级、教育、证书", "日期和年限分开解析"],
            ["证据成果", "成果量化、复杂度、规模、作品质量", "不凭描述长度给高分"],
            ["行为协作", "沟通、领导、问题解决、适应、冲突处理", "生成STAR类核验题"],
            ["工作约束", "薪资、地点、办公方式、出差、到岗时间", "识别否定词、开放区间和13-15薪"],
            ["发展偏好", "成长、行业、公司阶段、价值观和学习意愿", "用于求职者侧，不反向惩罚胜任度"],
        ], [29 * mm, 91 * mm, 54 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 4 * mm),
        p("岗位模板", styles["h2"]),
        p("内置 general、software_engineering、product_operations、sales_customer 四套模板。模板可覆盖基础系数，但仍受0-10范围校验；所有加载结果记录工作簿SHA-256、模板ID和实际系数，便于复现。", styles["body"]),
        PageBreak(),
    ])

    story.extend([
        p("05 双向匹配与四种结果状态", styles["h1"]),
        p("企业侧42项回答候选人对岗位的胜任度；求职者侧38项回答岗位对个人目标和现实约束的适配度。两侧先分别按已知项归一化，再用加权调和平均合成，避免单侧很高掩盖另一侧明显不合适。", styles["body"]),
        ScoreBars(font_name),
        styled_table([
            ["状态", "触发条件", "正式分", "报告动作"],
            ["ready_for_review", "无硬失败、无未核验硬项，资料达到阈值", "显示到小数点后2位", "进入人工复核"],
            ["insufficient_data", "整体资料或证据不足", "不显示", "列出高权重未知项"],
            [p("hard_requirement_<br/>unverified", styles["small"]), "存在必须条件，但候选人资料未知", "不显示", "先核验硬条件，不参与可比排序"],
            ["hard_failure", "确认未满足硬条件", "不显示", "说明失败门槛，保留人工复核"],
        ], [46 * mm, 70 * mm, 25 * mm, 33 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 4 * mm),
        p("边界处理", styles["h2"]),
        p("薪资区间仅在边界接触时记80分，不再当作完全匹配；开放区间保留空的上限或下限，13-15薪保留月份上下限。中文年限支持一年半、三年以上和三至五年。裸Java/Go保守按OR并标记待确认，若是硬条件则不显示正式分。到岗日期使用真实日历比较，并允许传入as_of_date固定基准日。", styles["body"]),
        PageBreak(),
    ])

    story.extend([
        p("06 四类角色报告怎样不同", styles["h1"]),
        p("同一个匹配结果不会换标题后重复输出。四类HTML报告在信息顺序、行动建议、问题类型和视觉强调上分别设计，每份包含5张内嵌SVG。", styles["body"]),
        styled_table([
            ["角色", "首屏重点", "后续内容", "主要行动"],
            ["HR", "匹配状态、硬条件、企业侧分数", "关键证据、风险、候选人顾虑、补证优先级", "决定下一步人工复核"],
            ["求职者", "岗位对个人的适配、现实约束", "个人亮点、差距、澄清问题、面试准备", "选择是否继续投入"],
            ["面试官", "待验证能力和证据强弱", "类型化题目、评分锚点、追问与记录栏", "保持候选人之间标准一致"],
            ["人才发展", "目标岗位准备度和迁移技能", "能力差距、证据缺口、学习任务、30/60/90天计划", "用于发展计划和复盘"],
        ], [24 * mm, 48 * mm, 68 * mm, 34 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 5 * mm),
        p("图表组成", styles["h2"]),
        styled_table([
            ["01 双向总览", "02 类别画像", "03 关键驱动", "04 资料完整度", "05 优先核验"],
            ["正式分或--", "低证据类别隐藏分数", "正向与风险因素", "已知、未知和来源", "下一步最值得问什么"],
        ], [34.8 * mm] * 5, styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 6 * mm),
        p("演示生成器一次输出4类常规角色报告、资料不足报告、硬条件待核验报告、公平性审计与30张SVG，方便现场答辩直接展示。", styles["callout"]),
        PageBreak(),
    ])

    story.extend([
        p("07 如何调用，以及适配哪些平台", styles["h1"]),
        p("核心只有Python标准库依赖；Excel读写、DOCX提取和HTML报告使用随项目提供的脚本。既可作为独立命令运行，也可接入支持命令行、标准输入或HTTP的编排平台。", styles["body"]),
        styled_table([
            ["调用方式", "适用环境", "入口"],
            ["CLI", "Windows、macOS、Linux、服务器、CI", p("scripts/interfaces/cli/<br/>talentlens.py", styles["small"])],
            ["NDJSON标准输入", "Claude Code、Codex、Gemini CLI、编辑器代理", p("scripts/interfaces/stdio/<br/>json_stdio.py", styles["small"])],
            ["本地HTTP", p("Dify、Coze、n8n、Flowise、<br/>LangChain、LlamaIndex", styles["small"]), p("scripts/interfaces/http/<br/>http_server.py", styles["small"])],
            ["AstronClaw", "SkillHub发布、平台安装与调用", "ZIP根目录SKILL.md"],
            ["角色封装", "HR、求职者、面试官、人才发展工作流", "scripts对应角色目录"],
        ], [31 * mm, 74 * mm, 69 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 5 * mm),
        p("推荐给通用智能助手的提示词", styles["h2"]),
        p("请调用 match-talent-opportunities，对候选人资料和岗位资料进行双向匹配。先检查硬条件和资料来源，再读取Excel中的80项系数；分别输出企业侧与求职者侧结果。未知字段不得按0分处理，存在未核验硬条件时不要展示正式匹配分。请生成适合当前角色的HTML报告和图表，并列出最优先补充的证据。基准日使用2026-07-15。", styles["callout"]),
        p("命令示例：python scripts/interfaces/cli/talentlens.py match --candidate candidate.json --job job.json --as-of-date 2026-07-15 --format json", styles["small"]),
        PageBreak(),
    ])

    story.extend([
        p("08 验收与工程质量", styles["h1"]),
        p("本轮检查把复检中的严重场景直接写入回归测试，包括中文数字年限与年月排除、跨行必须/优先作用域、斜杠歧义、顿号AND/OR、Go词边界、办公方式否定、开放薪资与薪资月数范围、公平性隔离、字段来源、证据脱敏和接口类型校验。", styles["body"]),
        styled_table([
            ["检查项", "结果", "说明"],
            ["自动测试", "122项全部通过", "测试运行器自动发现全部test_*.py"],
            ["指标完整性", "80/80", "Excel配置与实现一一对应"],
            ["异常输入", "500组无未捕获崩溃", "固定随机种子，可重复运行"],
            ["HTTP契约", "400 + 稳定错误码", "对象、数组和数组元素分别校验"],
            ["公平不变性", "分数差0.00", "敏感内容只审计，不参与评分"],
            ["演示图表", "30张SVG", "含资料不足和硬条件待核验两类边界报告"],
            ["ZIP结构", "根目录平铺", "打开后第一层直接看到SKILL.md"],
        ], [42 * mm, 43 * mm, 89 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 6 * mm),
        p("性能测量分冷启动和热路径：冷启动包含Excel读取与校验；热路径复用已加载配置。两种数据分开记录，避免把缓存效果写成全链路性能。", styles["callout"]),
        PageBreak(),
    ])

    story.extend([
        p("09 使用边界与提交说明", styles["h1"]),
        p("TalentLens是决策支持工具，不是自动招聘裁决器。所有角色报告都应由具备权限的人复核；受保护属性不应成为录用、淘汰、薪酬或晋升依据。真实平台中的鉴权、限流、日志留存和数据生命周期需要由部署方补齐。", styles["body"]),
        styled_table([
            ["提交前检查", "当前状态"],
            ["先修改源码目录，再生成ZIP", "已按此流程执行"],
            ["ZIP第一层包含SKILL.md、README.md、LICENSE.md", "离线验收脚本检查"],
            ["所有Python文件具有中文用途说明", "AST自动检查"],
            ["README说明不同用户、平台与提示词调用", "已覆盖"],
            ["Excel第一列为0-10影响系数", "运行时读取并校验"],
            ["不包含缓存、临时输出和无关散装脚本", "打包前清理"],
            ["AstronClaw真实上传、安装、调用和截图", "需在赛事平台账号中完成并留证"],
        ], [116 * mm, 58 * mm], styles, font_name=font_name, bold_name=bold_name),
        Spacer(1, 8 * mm),
        p("建议现场演示顺序", styles["h2"]),
        p("先展示同一对资料的HR与求职者报告差异；再删除一个硬条件字段，展示正式分变为“--”及补证问题；最后加入敏感岗位条件，展示审计报警但分数差仍为0.00。这个顺序能同时说明双向价值、结果可靠性和安全边界。", styles["callout"]),
        Spacer(1, 12 * mm),
        p("最终判断应由人作出，系统负责把依据讲清楚。", styles["h1"]),
    ])
    return story


def build_pdf(output_path: Path) -> Path:
    """生成PDF并返回最终路径。"""
    font_name, bold_name = register_fonts()
    styles = make_styles(font_name, bold_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=18 * mm,
        title="TalentLens 双向人才与机会匹配项目解释说明",
        author="TalentLens 项目组",
        subject="运行流程、匹配方法、角色输出与验收说明",
    )
    document.build(
        build_story(styles, font_name, bold_name),
        onFirstPage=lambda canvas, doc: header_footer(canvas, doc, font_name, bold_name),
        onLaterPages=lambda canvas, doc: header_footer(canvas, doc, font_name, bold_name),
    )
    return output_path


def main() -> int:
    """解析命令行参数并生成稳定命名的项目说明PDF。"""
    skill_root = Path(__file__).resolve().parents[3]
    default_output = skill_root.parent / "TalentLens-Project-Explanation.pdf"
    parser = argparse.ArgumentParser(description="生成TalentLens项目解释说明PDF")
    parser.add_argument("--output", type=Path, default=default_output, help="PDF输出路径")
    args = parser.parse_args()
    path = build_pdf(args.output.resolve())
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
