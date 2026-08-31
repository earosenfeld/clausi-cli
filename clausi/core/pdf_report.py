"""Polished, fully local PDF compliance report generation.

The PDF is built from the same findings and scan metadata as the Markdown
reports. ReportLab keeps generation deterministic and avoids a browser or
hosted rendering service in the report path.
"""

import subprocess
from datetime import datetime
from pathlib import Path
from textwrap import wrap
from typing import Any, Dict, Iterable, List, Optional
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from clausi.core.markdown_report import (
    REPORT_VERSION,
    SEVERITY_RANK,
    _apply_back_compat_defaults,
    _calculate_audit_readiness,
    _calculate_top_risk_themes,
    _real_findings,
    calculate_impact_score,
)


INK = HexColor("#071521")
INK_2 = HexColor("#0D2233")
SLATE_900 = HexColor("#172033")
SLATE_700 = HexColor("#3D4A5D")
SLATE_500 = HexColor("#6B778C")
SLATE_300 = HexColor("#CDD5DF")
SLATE_200 = HexColor("#E5EAF0")
SLATE_100 = HexColor("#F3F6F8")
SLATE_50 = HexColor("#F8FAFC")
CYAN = HexColor("#22D3EE")
CYAN_DARK = HexColor("#087F96")
RED = HexColor("#B4232C")
RED_BG = HexColor("#FCEBEC")
ORANGE = HexColor("#C75B12")
ORANGE_BG = HexColor("#FFF1E7")
AMBER = HexColor("#A46800")
AMBER_BG = HexColor("#FFF6D8")
GREEN = HexColor("#137A52")
GREEN_BG = HexColor("#E8F6EF")
BLUE_BG = HexColor("#E8F3F7")
WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
TOP_MARGIN = 22 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
# Usable width inside a finding card, which pads 9pt on each side. Laying a
# nested table out at full CONTENT_WIDTH pushed it past the card's own border
# by exactly that padding - visible as the metadata band bleeding outside the
# card frame on every evidence page.
CARD_PADDING = 9
CARD_INNER_WIDTH = CONTENT_WIDTH - 2 * CARD_PADDING

SEVERITY_COLORS = {
    "critical": (RED, RED_BG),
    "high": (ORANGE, ORANGE_BG),
    "medium": (AMBER, AMBER_BG),
    "warning": (AMBER, AMBER_BG),
    "low": (GREEN, GREEN_BG),
    "info": (CYAN_DARK, BLUE_BG),
}


class _ClausiCanvas(pdfcanvas.Canvas):
    """Draw a restrained document header and footer after page content."""

    def showPage(self) -> None:
        if self._pageNumber > 1:
            self.saveState()
            self.setStrokeColor(SLATE_200)
            self.setLineWidth(0.55)
            self.line(LEFT_MARGIN, PAGE_HEIGHT - 13 * mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 13 * mm)
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(INK_2)
            self.drawString(LEFT_MARGIN, PAGE_HEIGHT - 9 * mm, "CLAUSI")
            self.setFont("Helvetica", 7.2)
            self.setFillColor(SLATE_500)
            self.drawRightString(
                PAGE_WIDTH - RIGHT_MARGIN,
                PAGE_HEIGHT - 9 * mm,
                "CODE EVIDENCE ASSESSMENT",
            )
            self.setStrokeColor(SLATE_200)
            self.line(LEFT_MARGIN, 12 * mm, PAGE_WIDTH - RIGHT_MARGIN, 12 * mm)
            self.setFont("Helvetica", 7)
            self.setFillColor(SLATE_500)
            self.drawString(LEFT_MARGIN, 8 * mm, "Generated locally - human validation required")
            self.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 8 * mm, f"PAGE {self._pageNumber}")
            self.restoreState()
        super().showPage()


class _ClausiDocTemplate(SimpleDocTemplate):
    """Add PDF outline entries for marked section headings."""

    def afterFlowable(self, flowable: Any) -> None:
        outline = getattr(flowable, "_clausi_outline", None)
        if not outline:
            return
        title, key, level = outline
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)


def _clean(value: Any) -> str:
    """Normalize report text and enforce printable ASCII hyphens."""
    text = "" if value is None else str(value)
    for character in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(character, "-")
    return text


def _safe(value: Any) -> str:
    return escape(_clean(value)).replace("\n", "<br/>")


def _display_timestamp(value: Optional[str]) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.strftime("%B %d, %Y at %H:%M")
        except (TypeError, ValueError):
            pass
    return datetime.now().strftime("%B %d, %Y at %H:%M")


def _severity_counts(findings: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        severity = _clean(finding.get("severity", "info")).lower()
        if severity == "warning":
            severity = "medium"
        counts[severity if severity in counts else "info"] += 1
    return counts


def _git_provenance(project_path: Optional[Path]) -> Dict[str, str]:
    """Return repository provenance without requiring Git to be installed."""
    result = {"repository": "Not recorded", "branch": "Not recorded", "commit": "Not recorded"}
    if not project_path:
        return result
    path = Path(project_path).resolve()
    result["repository"] = path.name
    commands = {
        "repository": ["git", "-C", str(path), "remote", "get-url", "origin"],
        "branch": ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        "commit": ["git", "-C", str(path), "rev-parse", "HEAD"],
    }
    for key, command in commands.items():
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
        value = completed.stdout.strip()
        if completed.returncode == 0 and value:
            if key == "repository" and "://" in value:
                scheme, remainder = value.split("://", 1)
                authority, separator, suffix = remainder.partition("/")
                if "@" in authority:
                    authority = authority.rsplit("@", 1)[-1]
                value = f"{scheme}://{authority}{separator}{suffix}"
            result[key] = value
    if result["commit"] != "Not recorded":
        result["commit"] = result["commit"][:12]
    return result


def _status_copy(readiness: Dict[str, Any]) -> Dict[str, str]:
    if readiness["level"] == "not_ready":
        return {
            "label": "MATERIAL GAPS DETECTED",
            "title": "Hold formal review until critical findings are triaged",
            "body": (
                f"{readiness['blocking_count']} critical finding(s) require an owner, "
                "a treatment decision, and retained verification evidence."
            ),
            "color": "red",
        }
    if readiness["level"] == "partial":
        return {
            "label": "HIGH-PRIORITY GAPS DETECTED",
            "title": "Proceed only with an approved remediation plan",
            "body": (
                f"{readiness['high_count']} high-severity finding(s) should be triaged "
                "and assigned before review."
            ),
            "color": "orange",
        }
    return {
        "label": "NO MATERIAL GAPS DETECTED",
        "title": "Human validation is still required",
        "body": (
            "The automated scan did not flag critical or high-severity gaps in this scope. "
            "This is not a compliance determination."
        ),
        "color": "green",
    }


class PDFReportGenerator:
    """Generate the stakeholder PDF written beside Clausi's Markdown reports."""

    def __init__(self) -> None:
        self.styles = self._build_styles()

    def _section_heading(self, title: str, key: str) -> Paragraph:
        paragraph = Paragraph(_safe(title), self.styles["h1"])
        paragraph._clausi_outline = (title, key, 0)
        return paragraph

    def _build_styles(self) -> Dict[str, ParagraphStyle]:
        sample = getSampleStyleSheet()
        return {
            "cover_brand": ParagraphStyle(
                "CoverBrand", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=11, leading=14, textColor=INK_2, tracking=1.2, spaceAfter=6,
            ),
            "cover_eyebrow": ParagraphStyle(
                "CoverEyebrow", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=8, leading=11, tracking=1.6, textColor=CYAN_DARK, spaceAfter=9,
            ),
            "cover_title": ParagraphStyle(
                "CoverTitle", parent=sample["Title"], fontName="Helvetica-Bold",
                fontSize=28, leading=33, textColor=SLATE_900, alignment=TA_LEFT,
                spaceAfter=11,
            ),
            "cover_subtitle": ParagraphStyle(
                "CoverSubtitle", parent=sample["Normal"], fontName="Helvetica",
                fontSize=10.5, leading=16, textColor=SLATE_700, spaceAfter=20,
            ),
            "cover_project": ParagraphStyle(
                "CoverProject", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=18, leading=22, textColor=SLATE_900, spaceAfter=3,
            ),
            "cover_meta": ParagraphStyle(
                "CoverMeta", parent=sample["Normal"], fontName="Helvetica",
                fontSize=8.3, leading=12, textColor=SLATE_500,
            ),
            "h1": ParagraphStyle(
                "H1", parent=sample["Heading1"], fontName="Helvetica-Bold",
                fontSize=20, leading=25, textColor=SLATE_900, spaceAfter=7,
            ),
            "h2": ParagraphStyle(
                "H2", parent=sample["Heading2"], fontName="Helvetica-Bold",
                fontSize=15, leading=19, textColor=SLATE_900, spaceBefore=8,
                spaceAfter=8, keepWithNext=True,
            ),
            "h3": ParagraphStyle(
                "H3", parent=sample["Heading3"], fontName="Helvetica-Bold",
                fontSize=10.5, leading=14, textColor=SLATE_900, spaceAfter=4,
                keepWithNext=True,
            ),
            "eyebrow": ParagraphStyle(
                "Eyebrow", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=7.5, leading=10, tracking=1.2, textColor=CYAN_DARK,
                spaceAfter=5,
            ),
            "body": ParagraphStyle(
                "Body", parent=sample["BodyText"], fontName="Helvetica",
                fontSize=9.2, leading=14.2, textColor=SLATE_700, spaceAfter=7,
            ),
            "small": ParagraphStyle(
                "Small", parent=sample["BodyText"], fontName="Helvetica",
                fontSize=7.6, leading=11, textColor=SLATE_500,
            ),
            "small_bold": ParagraphStyle(
                "SmallBold", parent=sample["BodyText"], fontName="Helvetica-Bold",
                fontSize=7.8, leading=11, textColor=SLATE_700,
            ),
            "metric_value": ParagraphStyle(
                "MetricValue", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=17, leading=20, textColor=SLATE_900,
            ),
            "metric_label": ParagraphStyle(
                "MetricLabel", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=6.7, leading=9, tracking=0.7, textColor=SLATE_500,
            ),
            "code": ParagraphStyle(
                "Code", parent=sample["Code"], fontName="Courier",
                fontSize=7, leading=9.5, textColor=SLATE_900,
            ),
            "table_head": ParagraphStyle(
                "TableHead", parent=sample["Normal"], fontName="Helvetica-Bold",
                fontSize=7.2, leading=9, textColor=WHITE,
            ),
            "table_cell": ParagraphStyle(
                "TableCell", parent=sample["Normal"], fontName="Helvetica",
                fontSize=7.5, leading=10.5, textColor=SLATE_700,
            ),
            "finding_title": ParagraphStyle(
                "FindingTitle", parent=sample["Heading3"], fontName="Helvetica-Bold",
                fontSize=9.5, leading=12.5, textColor=SLATE_900, spaceAfter=3,
                keepWithNext=True,
            ),
            "note": ParagraphStyle(
                "Note", parent=sample["BodyText"], fontName="Helvetica",
                fontSize=7.2, leading=10.2, textColor=SLATE_500,
            ),
        }

    def save_report(
        self,
        findings: List[Dict[str, Any]],
        project_name: str,
        regulation: str,
        audit_meta: Dict[str, Any],
        output_dir: Path,
        files_scanned: int = 0,
        all_clauses: Optional[List[Dict[str, Any]]] = None,
        project_path: Optional[Path] = None,
        regulation_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write report.pdf and return its absolute path."""
        _apply_back_compat_defaults(findings)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "report.pdf"

        real_findings = sorted(
            _real_findings(findings), key=calculate_impact_score, reverse=True
        )
        clauses = all_clauses or []
        clause_titles = {
            _clean(clause.get("id")): _clean(clause.get("title")) for clause in clauses
        }
        readiness = _calculate_audit_readiness(real_findings)
        status = _status_copy(readiness)
        generated = _display_timestamp(audit_meta.get("timestamp"))
        provenance = _git_provenance(project_path)
        recorded_provenance = audit_meta.get("provenance") or {}
        if isinstance(recorded_provenance, dict):
            provenance.update({
                key: _clean(recorded_provenance[key])
                for key in ("repository", "branch", "commit")
                if recorded_provenance.get(key)
            })
        pack_metadata = regulation_metadata or {}

        document = _ClausiDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=RIGHT_MARGIN,
            leftMargin=LEFT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
            title=f"Clausi compliance evidence - {_clean(project_name)}",
            author="Clausi",
            subject=f"{_clean(regulation)} compliance scan",
        )
        story = self._build_story(
            real_findings,
            _clean(project_name),
            _clean(regulation),
            audit_meta,
            files_scanned,
            clauses,
            clause_titles,
            readiness,
            status,
            generated,
            provenance,
            pack_metadata,
        )
        document.build(
            story,
            onFirstPage=self._draw_cover_background,
            canvasmaker=_ClausiCanvas,
        )
        return str(output_path.resolve())

    def _build_story(
        self,
        findings: List[Dict[str, Any]],
        project_name: str,
        regulation: str,
        audit_meta: Dict[str, Any],
        files_scanned: int,
        clauses: List[Dict[str, Any]],
        clause_titles: Dict[str, str],
        readiness: Dict[str, Any],
        status: Dict[str, str],
        generated: str,
        provenance: Dict[str, str],
        pack_metadata: Dict[str, Any],
    ) -> List[Any]:
        story: List[Any] = []
        counts = _severity_counts(findings)
        total = len(findings)
        themes = _calculate_top_risk_themes(findings)
        material = counts["critical"] + counts["high"]
        clauses_with_gaps = len({
            _clean(finding.get("clause_id"))
            for finding in findings
            if finding.get("clause_id")
        })

        story.extend(self._cover(
            project_name,
            regulation,
            files_scanned,
            total,
            readiness,
            status,
            generated,
            provenance,
            pack_metadata,
        ))
        story.append(PageBreak())

        story.extend([
            Paragraph("EXECUTIVE DECISION", self.styles["eyebrow"]),
            self._section_heading("Assessment decision brief", "executive-decision"),
            Paragraph(
                "This page answers what was assessed, what requires attention, and what "
                "management should do next. It is an automated source-code assessment, "
                "not a certification or legal determination.",
                self.styles["body"],
            ),
            Spacer(1, 3 * mm),
            self._status_callout(status),
            Spacer(1, 5 * mm),
            self._metrics_table([
                (str(total), "TOTAL FINDINGS"),
                (str(material), "CRITICAL + HIGH"),
                (str(clauses_with_gaps), "CLAUSES WITH GAPS"),
                (str(files_scanned), "FILES ANALYZED"),
            ]),
            Spacer(1, 5 * mm),
            self._executive_overview(counts, themes, clause_titles),
            Spacer(1, 5 * mm),
            Paragraph("Management actions", self.styles["h2"]),
            self._management_actions(findings),
            Spacer(1, 4 * mm),
            self._change_summary(audit_meta),
        ])

        story.append(PageBreak())
        story.extend([
            Paragraph("ASSESSMENT BASIS", self.styles["eyebrow"]),
            self._section_heading("Scope, method, and provenance", "assessment-basis"),
            Paragraph(
                "These details define the boundary of the result and make the assessment "
                "reproducible. Items not represented in the scanned source require separate "
                "human or operational evidence.",
                self.styles["body"],
            ),
            Spacer(1, 3 * mm),
            self._scope_table(
                project_name,
                regulation,
                generated,
                files_scanned,
                len(clauses),
                audit_meta.get("provider"),
                audit_meta.get("model"),
                provenance,
                pack_metadata,
                audit_meta,
            ),
            Spacer(1, 7 * mm),
            Paragraph("Assessment limitations", self.styles["h2"]),
            self._limitations_table(),
        ])
        story.append(PageBreak())
        story.extend([
            Paragraph("ASSESSMENT BASIS", self.styles["eyebrow"]),
            Paragraph("Coverage and scoring definitions", self.styles["h1"]),
            Paragraph("Coverage-state definitions", self.styles["h2"]),
            self._coverage_legend(),
            Spacer(1, 6 * mm),
            Paragraph("Risk-rating method", self.styles["h2"]),
            self._risk_methodology(),
        ])
        story.extend(self._scan_coverage_block(audit_meta))

        story.append(PageBreak())
        story.extend([
            Paragraph("REMEDIATION WORKFLOW", self.styles["eyebrow"]),
            self._section_heading("Finding register and action plan", "remediation-register"),
            Paragraph(
                "Findings are ordered by materiality. Status, target date, and ticket fields "
                "are intentionally explicit so the report can support triage and follow-through.",
                self.styles["body"],
            ),
            Spacer(1, 3 * mm),
        ])
        if findings:
            register_page_size = 6
            for offset in range(0, len(findings), register_page_size):
                if offset:
                    story.extend([
                        Paragraph("REMEDIATION WORKFLOW", self.styles["eyebrow"]),
                        Paragraph("Finding register - continued", self.styles["h2"]),
                        Spacer(1, 2 * mm),
                    ])
                story.append(self._remediation_register(
                    findings[offset:offset + register_page_size], clause_titles
                ))
                if offset + register_page_size < len(findings):
                    story.append(PageBreak())
        else:
            story.append(self._empty_state(
                "No gaps were flagged",
                "No gap was returned for this scope. This is not proof of compliance; "
                "validate the assessment boundary and supporting evidence.",
            ))

        story.append(PageBreak())
        story.extend([
            Paragraph("EVIDENCE APPENDIX", self.styles["eyebrow"]),
            self._section_heading("Detailed findings and verification criteria", "evidence-appendix"),
            Paragraph(
                "Each record connects a requirement to an observed condition, source evidence, "
                "recommended treatment, and the evidence needed to close it.",
                self.styles["body"],
            ),
            Spacer(1, 3 * mm),
        ])
        if findings:
            for index, finding in enumerate(findings, 1):
                story.append(self._finding_card(index, finding, clause_titles))
                if index < len(findings):
                    story.append(PageBreak())
        else:
            story.append(self._empty_state(
                "No detailed findings",
                "No gaps were returned for this scan scope. Review the selected clauses, scanned files, and provider output before relying on the result.",
            ))

        if clauses:
            story.append(PageBreak())
            story.extend([
                Paragraph("CLAUSE COVERAGE", self.styles["eyebrow"]),
                self._section_heading("Traceability matrix", "traceability-matrix"),
                Paragraph(
                    "A clause-by-clause index of the automated result. A clause with no "
                    "finding remains subject to human validation and supporting evidence.",
                    self.styles["body"],
                ),
                Spacer(1, 3 * mm),
                self._coverage_table(findings, clauses),
            ])

        story.append(PageBreak())
        story.extend([
            Paragraph("REPORT CONTROL", self.styles["eyebrow"]),
            self._section_heading("Human review and disposition", "report-control"),
            Paragraph(
                "The automated result becomes a managed compliance record only after a "
                "qualified reviewer confirms scope, dispositions the findings, and retains "
                "the supporting evidence.",
                self.styles["body"],
            ),
            Spacer(1, 4 * mm),
            self._review_record(),
            Spacer(1, 8 * mm),
            Paragraph("Generation and data path", self.styles["h2"]),
            self._report_control_table(
                generated,
                audit_meta.get("provider"),
                audit_meta.get("model"),
                provenance,
                pack_metadata,
            ),
            Spacer(1, 7 * mm),
            self._data_path_note(),
            Spacer(1, 6 * mm),
            Paragraph(
                f"Report format version {REPORT_VERSION}. Automated compliance support "
                "software - not legal advice, certification, or a substitute for qualified review.",
                self.styles["small"],
            ),
        ])
        return story

    def _cover(
        self,
        project_name: str,
        regulation: str,
        files_scanned: int,
        total: int,
        readiness: Dict[str, Any],
        status: Dict[str, str],
        generated: str,
        provenance: Dict[str, str],
        pack_metadata: Dict[str, Any],
    ) -> List[Any]:
        return [
            Spacer(1, 4 * mm),
            Paragraph("CLAUSI", self.styles["cover_brand"]),
            Spacer(1, 32 * mm),
            Paragraph("AUTOMATED CODE EVIDENCE ASSESSMENT", self.styles["cover_eyebrow"]),
            Paragraph(f"{_safe(regulation)}<br/>Code Evidence Assessment", self.styles["cover_title"]),
            Paragraph(
                "Automated assessment of source-code evidence, potential control gaps, "
                "and remediation priorities for human review.",
                self.styles["cover_subtitle"],
            ),
            Spacer(1, 7 * mm),
            self._cover_document_control(
                project_name,
                generated,
                provenance,
                pack_metadata,
            ),
            Spacer(1, 11 * mm),
            self._cover_status(status),
            Spacer(1, 9 * mm),
            self._cover_metrics(files_scanned, total, readiness),
            Spacer(1, 19 * mm),
            Paragraph(
                "CUSTOMER REVIEW COPY",
                self.styles["cover_eyebrow"],
            ),
            Paragraph(
                "This report documents automated observations from the stated assessment "
                "scope. It is not legal advice, certification, or proof of compliance.",
                self.styles["cover_meta"],
            ),
        ]

    def _cover_document_control(
        self,
        project_name: str,
        generated: str,
        provenance: Dict[str, str],
        pack_metadata: Dict[str, Any],
    ) -> Table:
        version = _clean(pack_metadata.get("version")) or "Not recorded"
        rows = [
            [Paragraph("PROJECT", self.styles["metric_label"]), Paragraph(_safe(project_name), self.styles["cover_project"])],
            [Paragraph("ASSESSMENT DATE", self.styles["metric_label"]), Paragraph(_safe(generated), self.styles["cover_meta"])],
            [Paragraph("REPOSITORY", self.styles["metric_label"]), Paragraph(_safe(provenance["repository"]), self.styles["cover_meta"])],
            [Paragraph("COMMIT", self.styles["metric_label"]), Paragraph(_safe(provenance["commit"]), self.styles["cover_meta"])],
            [Paragraph("REGULATION PACK", self.styles["metric_label"]), Paragraph(_safe(version), self.styles["cover_meta"])],
        ]
        table = Table(rows, colWidths=[42 * mm, CONTENT_WIDTH - 42 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.7, SLATE_300),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _cover_status(self, status: Dict[str, str]) -> Table:
        accent, background = {
            "red": (RED, RED_BG),
            "orange": (ORANGE, ORANGE_BG),
            "green": (GREEN, GREEN_BG),
        }[status["color"]]
        label = Paragraph(
            f'<font color="{accent.hexval()}"><b>{_safe(status["label"])}</b></font>',
            self.styles["cover_meta"],
        )
        body = Paragraph(_safe(status["title"]), self.styles["small_bold"])
        # 54mm forced "HIGH-PRIORITY GAPS DETECTED" onto two cramped lines on
        # the cover; the verdict is the first thing a reader sees and should
        # not wrap.
        table = Table([[label, body]], colWidths=[62 * mm, CONTENT_WIDTH - 62 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("BOX", (0, 0), (-1, -1), 0.7, accent),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _cover_metrics(self, files: int, total: int, readiness: Dict[str, Any]) -> Table:
        data = []
        for value, label in (
            (files, "FILES SCANNED"),
            (total, "FINDINGS"),
            (readiness["blocking_count"], "CRITICAL"),
        ):
            data.append([
                Paragraph(f"<b>{value}</b>", self.styles["metric_value"]),
                Paragraph(label, self.styles["metric_label"]),
            ])
        table = Table([data], colWidths=[CONTENT_WIDTH / 3] * 3)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _status_callout(self, status: Dict[str, str]) -> Table:
        accent, background = {
            "red": (RED, RED_BG), "orange": (ORANGE, ORANGE_BG), "green": (GREEN, GREEN_BG)
        }[status["color"]]
        content = [
            Paragraph(
                f'<font color="{accent.hexval()}"><b>{_safe(status["label"])}</b></font>',
                self.styles["small"],
            ),
            Spacer(1, 2),
            Paragraph(_safe(status["title"]), self.styles["h3"]),
            Paragraph(_safe(status["body"]), self.styles["body"]),
        ]
        table = Table([[content]], colWidths=[CONTENT_WIDTH])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 13),
            ("RIGHTPADDING", (0, 0), (-1, -1), 13),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _metrics_table(self, metrics: List[Any]) -> Table:
        cells = []
        for value, label in metrics:
            cells.append([
                Paragraph(_safe(value), self.styles["metric_value"]),
                Paragraph(_safe(label), self.styles["metric_label"]),
            ])
        table = Table([cells], colWidths=[CONTENT_WIDTH / len(cells)] * len(cells))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        return table

    def _executive_overview(
        self,
        counts: Dict[str, int],
        themes: List[Dict[str, Any]],
        titles: Dict[str, str],
    ) -> Table:
        left = [
            Paragraph("RISK DISTRIBUTION", self.styles["eyebrow"]),
            self._severity_compact(counts),
        ]
        right = [
            Paragraph("CONCENTRATED RISK AREAS", self.styles["eyebrow"]),
            self._themes_compact(themes[:4], titles),
        ]
        table = Table([[left, right]], colWidths=[CONTENT_WIDTH * 0.48, CONTENT_WIDTH * 0.52])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, -1), 8),
            ("LEFTPADDING", (1, 0), (1, -1), 8),
            ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ]))
        return table

    def _themes_compact(
        self,
        themes: List[Dict[str, Any]],
        titles: Dict[str, str],
    ) -> Table:
        if not themes:
            return self._empty_state("No grouped risks", "No risk themes were available.")
        rows = []
        for theme in themes:
            name = titles.get(_clean(theme["name"]), _clean(theme["name"]))
            rows.append([
                Paragraph(_safe(name), self.styles["table_cell"]),
                Paragraph(str(theme["count"]), self.styles["small_bold"]),
            ])
        width = CONTENT_WIDTH * 0.52 - 8
        table = Table(rows, colWidths=[width - 18 * mm, 18 * mm])
        table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, SLATE_200),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _severity_compact(self, counts: Dict[str, int]) -> Table:
        rows = []
        for severity in ("critical", "high", "medium", "low", "info"):
            accent, background = SEVERITY_COLORS[severity]
            rows.append([
                Paragraph(
                    f'<font color="{accent.hexval()}"><b>{severity.upper()}</b></font>',
                    self.styles["small"],
                ),
                Paragraph(str(counts[severity]), self.styles["small_bold"]),
            ])
        width = CONTENT_WIDTH * 0.48 - 8
        table = Table(rows, colWidths=[width - 18 * mm, 18 * mm])
        table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, SLATE_200),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _management_actions(self, findings: List[Dict[str, Any]]) -> Table:
        rows: List[List[Any]] = [[
            Paragraph("FINDING", self.styles["table_head"]),
            Paragraph("DECISION REQUIRED", self.styles["table_head"]),
            Paragraph("OWNER", self.styles["table_head"]),
            Paragraph("DUE / STATUS", self.styles["table_head"]),
        ]]
        for index, finding in enumerate(findings[:5], 1):
            finding_id = _clean(finding.get("finding_id")) or f"F-{index:03d}"
            treatment = _clean(
                finding.get("treatment")
                or finding.get("recommended_solution")
                or "Document a treatment decision."
            )
            if len(treatment) > 180:
                treatment = treatment[:177].rstrip() + "..."
            owner = _clean(finding.get("owner") or finding.get("responsible_party")) or "Unassigned"
            target = _clean(finding.get("target_date")) or "TBD"
            status = _clean(finding.get("status")) or "Open"
            rows.append([
                Paragraph(f'<link href="#{_safe(finding_id)}" color="{CYAN_DARK.hexval()}"><b>{_safe(finding_id)}</b></link>', self.styles["small"]),
                Paragraph(_safe(treatment), self.styles["table_cell"]),
                Paragraph(_safe(owner), self.styles["table_cell"]),
                Paragraph(f"{_safe(target)}<br/>{_safe(status)}", self.styles["table_cell"]),
            ])
        if len(rows) == 1:
            rows.append([
                Paragraph("-", self.styles["table_cell"]),
                Paragraph("Confirm scope and retain supporting evidence.", self.styles["table_cell"]),
                Paragraph("Compliance", self.styles["table_cell"]),
                Paragraph("TBD / Open", self.styles["table_cell"]),
            ])
        table = Table(rows, colWidths=[31 * mm, CONTENT_WIDTH - 78 * mm, 24 * mm, 23 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK_2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _change_summary(self, audit_meta: Dict[str, Any]) -> Table:
        changes = audit_meta.get("change_summary") or {}
        baseline = bool(audit_meta.get("comparison_baseline", not changes))
        if baseline:
            detail = "Baseline assessment - all current findings are new; future scans will compare against this snapshot."
        else:
            detail = (
                f"{changes.get('new', 0)} new | {changes.get('changed', 0)} changed | "
                f"{changes.get('reopened', 0)} reopened | {changes.get('resolved', 0)} no longer detected | "
                f"{changes.get('unchanged', 0)} unchanged"
            )
        table = Table([[
            Paragraph("CHANGE SINCE PRIOR ASSESSMENT", self.styles["metric_label"]),
            Paragraph(_safe(detail), self.styles["small"]),
        ]], colWidths=[55 * mm, CONTENT_WIDTH - 55 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _severity_table(self, counts: Dict[str, int]) -> Table:
        maximum = max(max(counts.values()), 1)
        rows = []
        for severity in ("critical", "high", "medium", "low", "info"):
            count = counts[severity]
            accent, _ = SEVERITY_COLORS[severity]
            drawing = Drawing(95 * mm, 5 * mm)
            drawing.add(Rect(0, 1.5 * mm, 95 * mm, 2 * mm, fillColor=SLATE_100, strokeColor=None))
            if count:
                drawing.add(Rect(
                    0, 1.5 * mm, max(3 * mm, 95 * mm * count / maximum), 2 * mm,
                    fillColor=accent, strokeColor=None,
                ))
            rows.append([
                Paragraph(f'<font color="{accent.hexval()}"><b>{severity.upper()}</b></font>', self.styles["small"]),
                drawing,
                Paragraph(str(count), self.styles["small_bold"]),
            ])
        table = Table(rows, colWidths=[29 * mm, 102 * mm, CONTENT_WIDTH - 131 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    def _themes_table(self, themes: List[Dict[str, Any]], titles: Dict[str, str]) -> Table:
        if not themes:
            return self._empty_state("No risk themes", "No grouped findings were available for this scan.")
        rows = []
        for index, theme in enumerate(themes, 1):
            name = titles.get(_clean(theme["name"]), _clean(theme["name"]))
            rows.append([
                Paragraph(f"{index:02d}", self.styles["small_bold"]),
                Paragraph(f"<b>{_safe(name)}</b>", self.styles["body"]),
                Paragraph(f"{theme['count']} finding(s)", self.styles["small"]),
            ])
        table = Table(rows, colWidths=[13 * mm, CONTENT_WIDTH - 47 * mm, 34 * mm])
        style = [
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        table.setStyle(TableStyle(style))
        return table

    def _priority_items(self, findings: List[Dict[str, Any]], titles: Dict[str, str]) -> List[Any]:
        items: List[Any] = []
        for index, finding in enumerate(findings, 1):
            severity = _clean(finding.get("severity", "info")).lower()
            accent, background = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])
            clause = _clean(finding.get("clause_id", "Unmapped requirement"))
            title = titles.get(clause) or _clean(finding.get("statement")) or clause
            content = [
                Paragraph(
                    f'<font color="{accent.hexval()}"><b>{index:02d} / {severity.upper()}</b></font>',
                    self.styles["small"],
                ),
                Paragraph(f"<b>{_safe(clause)}</b> - {_safe(title)}", self.styles["h3"]),
                Paragraph(_safe(finding.get("explanation")), self.styles["body"]),
                Paragraph(
                    f'<b>Owner:</b> {_safe(finding.get("responsible_party", "Engineering"))} &nbsp;&nbsp; '
                    f'<b>Complexity:</b> {_safe(finding.get("remediation_complexity", "Medium"))} &nbsp;&nbsp; '
                    f'<b>Location:</b> {_safe(self._location(finding))}',
                    self.styles["small"],
                ),
            ]
            table = Table([[content]], colWidths=[CONTENT_WIDTH])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            items.extend([table, Spacer(1, 3 * mm)])
        return items

    def _scope_table(
        self,
        project_name: str,
        regulation: str,
        generated: str,
        files_scanned: int,
        clauses_scanned: int,
        provider: Any,
        model: Any,
        provenance: Dict[str, str],
        pack_metadata: Dict[str, Any],
        audit_meta: Dict[str, Any],
    ) -> Table:
        pack_version = _clean(pack_metadata.get("version")) or "Not recorded"
        effective_date = _clean(pack_metadata.get("effective_date")) or "Not recorded"
        last_updated = _clean(pack_metadata.get("last_updated")) or "Not recorded"
        file_types = audit_meta.get("file_types") or {}
        type_summary = ", ".join(f".{key}: {value}" for key, value in file_types.items()) or "Not recorded"
        total_bytes = audit_meta.get("total_bytes")
        byte_summary = f"{int(total_bytes):,} bytes" if isinstance(total_bytes, (int, float)) else "Not recorded"
        pack_hash = _clean(audit_meta.get("regulation_pack_sha256"))
        pack_hash = pack_hash[:16] + "..." if pack_hash else "Not recorded"
        rows = [
            ("Assessment type", "Automated source-code evidence review"),
            ("Project", project_name),
            ("Repository", provenance["repository"]),
            ("Branch / commit", f"{provenance['branch']} / {provenance['commit']}"),
            ("Regulation pack", f"{regulation} - version {pack_version}"),
            ("Pack dates", f"Effective {effective_date}; updated {last_updated}"),
            ("Generated", generated),
            ("Files discovered / analyzed", f"{audit_meta.get('files_discovered', files_scanned)} / {files_scanned}"),
            ("Files ignored", str(audit_meta.get("files_ignored", 0))),
            ("Analyzed file types", type_summary),
            ("Analyzed source size", byte_summary),
            ("Clauses evaluated", str(clauses_scanned) if clauses_scanned else "Not recorded"),
            ("Scope boundary", f"{_clean(audit_meta.get('clausiignore')) or 'No .clausiignore'}; CLI patterns: {_clean(audit_meta.get('ignore_patterns')) or 'none'}"),
            ("AI provider / model", f"{_clean(provider) or 'Not recorded'} / {_clean(model) or 'Not recorded'}"),
            ("Regulation pack SHA-256", pack_hash),
            ("Reproduction command", _clean(audit_meta.get("scan_command")) or "Not recorded"),
        ]
        data = [
            [Paragraph(_safe(label), self.styles["small_bold"]), Paragraph(_safe(value), self.styles["table_cell"])]
            for label, value in rows
        ]
        table = Table(data, colWidths=[42 * mm, CONTENT_WIDTH - 42 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _limitations_table(self) -> Table:
        limitations = [
            (
                "Source-code boundary",
                "The scan evaluates available text-based source and configuration files. "
                "It does not by itself verify policies, contracts, production behavior, or operational controls.",
            ),
            (
                "Automated interpretation",
                "Findings may contain false positives or miss context outside the scanned files. "
                "Severity and remediation guidance require qualified human review.",
            ),
            (
                "Risk-rating basis",
                "Severity is an automated prioritization signal. Organization-specific "
                "likelihood, impact, and risk acceptance require human calibration.",
            ),
            (
                "No-gap result",
                "No finding means no gap was detected in this scope; it does not establish compliance.",
            ),
            (
                "Point-in-time evidence",
                "The result reflects the recorded commit or project snapshot and may become stale after changes.",
            ),
        ]
        data = [
            [Paragraph(_safe(label), self.styles["small_bold"]), Paragraph(_safe(body), self.styles["table_cell"])]
            for label, body in limitations
        ]
        table = Table(data, colWidths=[39 * mm, CONTENT_WIDTH - 39 * mm])
        table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _coverage_legend(self) -> Table:
        states = [
            ("Gap detected", "One or more findings are mapped to the clause."),
            ("No gap detected", "No finding was returned; human validation remains required."),
            ("Not assessed", "The clause was outside the selected scan scope."),
            ("Insufficient evidence", "The available files do not support a reliable conclusion."),
        ]
        rows = [
            [Paragraph(_safe(state), self.styles["small_bold"]), Paragraph(_safe(meaning), self.styles["table_cell"])]
            for state, meaning in states
        ]
        table = Table(rows, colWidths=[39 * mm, CONTENT_WIDTH - 39 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _scan_coverage_block(self, audit_meta: Dict[str, Any]) -> List[Any]:
        """What this scan did not examine.

        The report is only as strong as its coverage, and this is the artifact
        an assessor actually reads - so the exclusions belong here, not only in
        scan_manifest.json. Absence of a finding for anything listed below means
        it was not examined, which is not the same as compliant.
        """
        coverage = audit_meta.get("coverage") or {}
        unsupported = coverage.get("skipped_unsupported_extension") or {}
        excluded_dirs = coverage.get("skipped_excluded_directories") or {}
        unreadable = coverage.get("unreadable") or []
        ignored = audit_meta.get("ignored_files") or []
        truncated = audit_meta.get("truncated_files") or []
        failed = audit_meta.get("failed_files") or []
        not_assessed = audit_meta.get("not_assessed") or []

        rows = []
        if unsupported:
            total = sum(unsupported.values())
            top = ", ".join(f"{ext} ({n})" for ext, n in list(unsupported.items())[:6])
            rows.append(("Unsupported file types", f"{total} file(s) not read - {top}"))
        if excluded_dirs:
            total = sum(excluded_dirs.values())
            top = ", ".join(f"{name}" for name in list(excluded_dirs)[:6])
            rows.append((
                "Excluded directories",
                f"{total} directory(ies) skipped as dependency, build, cache, or Clausi output - {top}",
            ))
        if ignored:
            rows.append((
                "Excluded by ignore rules",
                f"{len(ignored)} file(s) excluded by .clausiignore or --ignore",
            ))
        if unreadable:
            rows.append(("Could not be read", f"{len(unreadable)} file(s) failed to open"))
        if truncated:
            rows.append((
                "Partially examined",
                f"{len(truncated)} file(s) exceeded the per-file character limit; only the "
                "beginning of each was analyzed",
            ))
        if failed:
            rows.append((
                "Failed during analysis",
                f"{len(failed)} file(s) returned an error from the AI provider and produced "
                "no findings",
            ))

        if not_assessed:
            by_reason: Dict[str, int] = {}
            for entry in not_assessed:
                reason = entry.get("reason", "insufficient_context")
                by_reason[reason] = by_reason.get(reason, 0) + 1
            detail = ", ".join(
                f"{r.replace('_', ' ')} ({n})" for r, n in by_reason.items()
            )
            rows.append((
                "Clauses not assessed",
                f"{len(not_assessed)} clause/file pair(s) the analysis declined to judge "
                f"- {detail}. An abstention is not a pass; nothing was concluded",
            ))

        if not rows:
            return []

        table_rows = [
            [Paragraph(_safe(label), self.styles["small_bold"]),
             Paragraph(_safe(detail), self.styles["table_cell"])]
            for label, detail in rows
        ]
        table = Table(table_rows, colWidths=[45 * mm, CONTENT_WIDTH - 45 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [
            Spacer(1, 6 * mm),
            Paragraph("Scan coverage and exclusions", self.styles["h2"]),
            Paragraph(
                "This assessment covers only the files recorded as analyzed. The items below "
                "were not examined, or were examined only in part. Absence of a finding for "
                "any of them does not indicate compliance. The complete file-level record is "
                "in scan_manifest.json alongside this report.",
                self.styles["body"],
            ),
            Spacer(1, 3 * mm),
            table,
        ]

    def _risk_methodology(self) -> Table:
        rows = [
            ("Impact (1-5)", "Consequence within the stated scan scope. When the provider omits a score, Clausi shows a severity-derived proxy and labels that basis."),
            ("Likelihood (1-5)", "Probability supported by source evidence. If evidence is insufficient, likelihood remains blank rather than being invented."),
            ("Risk score", "Impact x likelihood. 1-5 Low; 6-11 Medium; 12-19 High; 20-25 Critical."),
            ("Human calibration", "A qualified reviewer must validate scores, record treatment, and approve any risk acceptance."),
        ]
        data = [
            [Paragraph(_safe(label), self.styles["small_bold"]), Paragraph(_safe(body), self.styles["table_cell"])]
            for label, body in rows
        ]
        table = Table(data, colWidths=[39 * mm, CONTENT_WIDTH - 39 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _remediation_register(
        self,
        findings: List[Dict[str, Any]],
        titles: Dict[str, str],
    ) -> LongTable:
        data: List[Any] = [[
            Paragraph("ID", self.styles["table_head"]),
            Paragraph("RISK", self.styles["table_head"]),
            Paragraph("REQUIREMENT", self.styles["table_head"]),
            Paragraph("CONDITION AND TREATMENT", self.styles["table_head"]),
            Paragraph("OWNER", self.styles["table_head"]),
            Paragraph("TARGET", self.styles["table_head"]),
            Paragraph("STATUS", self.styles["table_head"]),
        ]]
        for index, finding in enumerate(findings, 1):
            severity = _clean(finding.get("severity", "info")).upper()
            finding_id = _clean(finding.get("finding_id")) or f"F-{index:03d}"
            clause = _clean(finding.get("clause_id", "Unmapped"))
            title = titles.get(clause) or _clean(finding.get("statement")) or "Requirement"
            condition = _clean(finding.get("explanation") or finding.get("violation"))
            plan = _clean(
                finding.get("recommended_solution")
                or finding.get("recommendation")
                or "Treatment decision required"
            )
            owner = _clean(finding.get("responsible_party")) or "Unassigned"
            target = _clean(finding.get("target_date") or finding.get("due_date")) or "TBD"
            status = _clean(finding.get("status")) or "Open"
            risk_score = finding.get("risk_score")
            risk_label = _clean(finding.get("risk_rating")) or "Not scored"
            change = _clean(finding.get("change_status")) or "new"
            data.append([
                Paragraph(f'<link href="#{_safe(finding_id)}" color="{CYAN_DARK.hexval()}">{_safe(finding_id)}</link>', self.styles["table_cell"]),
                Paragraph(f"<b>{_safe(severity)}</b><br/>{_safe(risk_label)}{f' / {risk_score}' if risk_score else ''}<br/>{_safe(change.title())}", self.styles["small"]),
                Paragraph(f"<b>{_safe(clause)}</b><br/>{_safe(title)}", self.styles["table_cell"]),
                Paragraph(
                    f"<b>Condition:</b> {_safe(condition)}<br/><b>Plan:</b> {_safe(plan)}",
                    self.styles["table_cell"],
                ),
                Paragraph(_safe(owner), self.styles["table_cell"]),
                Paragraph(_safe(target), self.styles["table_cell"]),
                Paragraph(_safe(status), self.styles["table_cell"]),
            ])
        # TARGET and STATUS were 13mm, which after padding left ~3mm of text
        # column - narrow enough that ReportLab broke the single-word headers
        # mid-word ("TARGE T", "STATU S") in the rendered PDF.
        widths = [30 * mm, 18 * mm, 24 * mm, 50 * mm, 20 * mm, 16 * mm, 16 * mm]
        table = LongTable(data, repeatRows=1, colWidths=widths)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), INK_2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for row_index, finding in enumerate(findings, 1):
            severity = _clean(finding.get("severity", "info")).lower()
            accent, _ = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])
            style.append(("LINEBEFORE", (1, row_index), (1, row_index), 2.2, accent))
        table.setStyle(TableStyle(style))
        return table

    def _finding_card(self, index: int, finding: Dict[str, Any], titles: Dict[str, str]) -> Table:
        severity = _clean(finding.get("severity", "info")).lower()
        accent, background = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])
        clause = _clean(finding.get("clause_id", "Unmapped requirement"))
        clause_title = titles.get(clause) or _clean(finding.get("statement")) or "Requirement"
        condition = _clean(finding.get("explanation") or finding.get("violation"))
        evidence = _clean(finding.get("evidence")) or "No separate evidence narrative was returned."
        impact = _clean(finding.get("why_this_matters")) or (
            "Potential regulatory and operational impact requires human validation."
        )
        recommendation = _clean(
            finding.get("recommended_solution")
            or finding.get("recommendation")
            or "Document a treatment decision and supporting evidence."
        )
        verification = _clean(
            finding.get("verification_criteria")
            or finding.get("acceptance_criteria")
            or "Retest the affected path, confirm the control operates as intended, and retain evidence."
        )
        certainty = _clean(finding.get("finding_certainty"))
        if not certainty and isinstance(finding.get("confidence"), (int, float)):
            certainty = f"{round(float(finding['confidence']) * 100)}%"
        certainty = certainty or "Not recorded"
        owner = _clean(finding.get("responsible_party")) or "Unassigned"
        target = _clean(finding.get("target_date") or finding.get("due_date")) or "TBD"
        finding_status = _clean(finding.get("status")) or "Open"
        ticket = _clean(finding.get("ticket") or finding.get("ticket_id")) or "Not linked"
        finding_id = _clean(finding.get("finding_id")) or f"F-{index:03d}"
        change = _clean(finding.get("change_status")) or "new"
        impact_score = finding.get("impact_score")
        likelihood_score = finding.get("likelihood_score")
        risk_score = finding.get("risk_score")
        risk_rating = _clean(finding.get("risk_rating")) or "Not scored"
        risk_rationale = _clean(finding.get("risk_rationale")) or "Human calibration required."

        header = Table([
            [
                Paragraph(
                    f'<a name="{_safe(finding_id)}"/><font color="{CYAN_DARK.hexval()}"><b>{_safe(finding_id)}</b></font> &nbsp; '
                    f'<b>{_safe(clause)} - {_safe(clause_title)}</b>',
                    self.styles["finding_title"],
                ),
                Paragraph(
                    f'<font color="{accent.hexval()}"><b>{severity.upper()}</b></font>',
                    self.styles["small"],
                ),
            ]
        ], colWidths=[CARD_INNER_WIDTH - 31 * mm, 31 * mm])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))

        metadata = Table([
            [
                Paragraph(f'<b>LOCATION</b><br/>{_safe(self._location(finding))}', self.styles["small"]),
                Paragraph(f'<b>CONFIDENCE</b><br/>{_safe(certainty)}', self.styles["small"]),
                Paragraph(f'<b>CHANGE</b><br/>{_safe(change.title())}', self.styles["small"]),
                Paragraph(f'<b>RISK</b><br/>{_safe(risk_rating)}{f" / {risk_score}" if risk_score else ""}', self.styles["small"]),
            ],
            [
                Paragraph(f'<b>OWNER</b><br/>{_safe(owner)}', self.styles["small"]),
                Paragraph(f'<b>TARGET</b><br/>{_safe(target)}', self.styles["small"]),
                Paragraph(f'<b>STATUS</b><br/>{_safe(finding_status)}', self.styles["small"]),
                Paragraph(f'<b>TICKET</b><br/>{_safe(ticket)}', self.styles["small"]),
            ],
        ], colWidths=[CARD_INNER_WIDTH * 0.42, CARD_INNER_WIDTH * 0.18,
                       CARD_INNER_WIDTH * 0.18, CARD_INNER_WIDTH * 0.22])
        metadata.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        left: List[Any] = [
            Paragraph("OBSERVED CONDITION", self.styles["eyebrow"]),
            Paragraph(_safe(condition), self.styles["table_cell"]),
            Spacer(1, 2 * mm),
            Paragraph("SOURCE EVIDENCE", self.styles["eyebrow"]),
            Paragraph(_safe(evidence), self.styles["table_cell"]),
        ]
        if finding.get("code_snippet"):
            left.extend([
                Spacer(1, 2 * mm),
                self._code_block(
                    _clean(finding["code_snippet"]),
                    max_lines=5,
                    available_width=(CONTENT_WIDTH - 18) / 2,
                ),
            ])
        right: List[Any] = [
            Paragraph("WHY IT MATTERS", self.styles["eyebrow"]),
            Paragraph(_safe(impact), self.styles["table_cell"]),
            Spacer(1, 2 * mm),
            Paragraph("RISK BASIS", self.styles["eyebrow"]),
            Paragraph(
                f"Impact {_safe(impact_score or 'not recorded')} / 5; likelihood {_safe(likelihood_score or 'not assessed')} / 5. {_safe(risk_rationale)}",
                self.styles["table_cell"],
            ),
            Spacer(1, 2 * mm),
            Paragraph("RECOMMENDED TREATMENT", self.styles["eyebrow"]),
            Paragraph(_safe(recommendation), self.styles["table_cell"]),
            Spacer(1, 2 * mm),
            Paragraph("CLOSURE EVIDENCE", self.styles["eyebrow"]),
            Paragraph(_safe(verification), self.styles["table_cell"]),
        ]
        detail = Table([[left, right]], colWidths=[CARD_INNER_WIDTH / 2] * 2)
        detail.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEAFTER", (0, 0), (0, -1), 0.45, SLATE_200),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, -1), 9),
            ("LEFTPADDING", (1, 0), (1, -1), 9),
            ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ]))

        card = Table([[[header, Spacer(1, 2 * mm), metadata, Spacer(1, 3 * mm), detail]]], colWidths=[CONTENT_WIDTH])
        card.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, SLATE_200),
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("LEFTPADDING", (0, 0), (-1, -1), CARD_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), CARD_PADDING),
            ("TOPPADDING", (0, 0), (-1, -1), CARD_PADDING),
            ("BOTTOMPADDING", (0, 0), (-1, -1), CARD_PADDING),
        ]))
        return card

    def _coverage_table(self, findings: List[Dict[str, Any]], clauses: List[Dict[str, Any]]) -> LongTable:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        finding_ids = {
            id(finding): (_clean(finding.get("finding_id")) or f"F-{index:03d}")
            for index, finding in enumerate(findings, 1)
        }
        for finding in findings:
            grouped.setdefault(_clean(finding.get("clause_id")), []).append(finding)
        data: List[Any] = [[
            Paragraph("CLAUSE", self.styles["table_head"]),
            Paragraph("REQUIREMENT", self.styles["table_head"]),
            Paragraph("FINDING IDS", self.styles["table_head"]),
            Paragraph("ASSESSMENT STATE", self.styles["table_head"]),
        ]]
        for clause in clauses:
            clause_id = _clean(clause.get("id"))
            clause_findings = grouped.get(clause_id, [])
            worst = min(
                (SEVERITY_RANK.get(_clean(f.get("severity", "medium")).lower(), 2) for f in clause_findings),
                default=99,
            )
            result = "Gap detected" if clause_findings else "No gap detected - human validation required"
            if worst == 0:
                result = "Gap detected - critical"
            elif worst == 1:
                result = "Gap detected - high"
            ids = ", ".join(
                f'<link href="#{_safe(finding_ids[id(finding)])}" color="{CYAN_DARK.hexval()}">{_safe(finding_ids[id(finding)])}</link>'
                for finding in clause_findings
            ) or "-"
            data.append([
                Paragraph(_safe(clause_id), self.styles["table_cell"]),
                Paragraph(_safe(clause.get("title")), self.styles["table_cell"]),
                Paragraph(ids, self.styles["table_cell"]),
                Paragraph(_safe(result), self.styles["table_cell"]),
            ])
        table = LongTable(
            data,
            repeatRows=1,
            colWidths=[27 * mm, CONTENT_WIDTH - 92 * mm, 29 * mm, 36 * mm],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK_2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SLATE_50]),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _code_block(
        self,
        code: str,
        max_lines: int = 8,
        available_width: Optional[float] = None,
    ) -> Table:
        lines: List[str] = []
        wrap_width = 44 if available_width and available_width < CONTENT_WIDTH * 0.75 else 88
        for line in code.splitlines() or [""]:
            if len(line) <= wrap_width:
                lines.append(line)
            else:
                indentation = len(line) - len(line.lstrip())
                prefix = " " * min(indentation, 16)
                wrapped = wrap(
                    line,
                    width=wrap_width,
                    subsequent_indent=prefix + "  ",
                    replace_whitespace=False,
                )
                lines.extend(wrapped or [line])
        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["... excerpt truncated ..."]
        pre = Preformatted("\n".join(lines), self.styles["code"])
        width = available_width or CONTENT_WIDTH
        table = Table([[pre]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _empty_state(self, title: str, body: str) -> Table:
        table = Table([[[
            Paragraph(_safe(title), self.styles["h3"]),
            Paragraph(_safe(body), self.styles["body"]),
        ]]], colWidths=[CONTENT_WIDTH])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    def _report_control_table(
        self,
        generated: str,
        provider: Any,
        model: Any,
        provenance: Dict[str, str],
        pack_metadata: Dict[str, Any],
    ) -> Table:
        rows = [
            ("Generated", generated),
            ("Clausi report format", REPORT_VERSION),
            ("Repository", provenance["repository"]),
            ("Branch / commit", f"{provenance['branch']} / {provenance['commit']}"),
            ("Regulation pack version", _clean(pack_metadata.get("version")) or "Not recorded"),
            ("Provider / model", f"{_clean(provider) or 'Not recorded'} / {_clean(model) or 'Not recorded'}"),
        ]
        data = [
            [Paragraph(_safe(label), self.styles["small_bold"]), Paragraph(_safe(value), self.styles["table_cell"])]
            for label, value in rows
        ]
        table = Table(data, colWidths=[45 * mm, CONTENT_WIDTH - 45 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), SLATE_100),
            ("BOX", (0, 0), (-1, -1), 0.6, SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _data_path_note(self) -> Table:
        table = Table([[[
            Paragraph("DATA PATH", self.styles["eyebrow"]),
            Paragraph(
                "Report generation occurred locally. Relevant code snippets may have been "
                "sent directly to the AI provider selected for the scan under the customer's "
                "own account. Clausi infrastructure is not in that data path.",
                self.styles["body"],
            ),
        ]]], colWidths=[CONTENT_WIDTH])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BLUE_BG),
            ("LINEBEFORE", (0, 0), (0, -1), 3, CYAN_DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    def _review_record(self) -> Table:
        rows = []
        for label in (
            "Reviewed by",
            "Role / function",
            "Review date",
            "Disposition",
            "Approval or ticket",
        ):
            rows.append([
                Paragraph(label, self.styles["small_bold"]),
                Paragraph("____________________________________________________________", self.styles["small"]),
            ])
        table = Table(rows, colWidths=[35 * mm, CONTENT_WIDTH - 35 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    @staticmethod
    def _location(finding: Dict[str, Any]) -> str:
        file_path = _clean(finding.get("file_path") or "Unknown file")
        location = _clean(finding.get("location"))
        if not location:
            start = finding.get("line_start")
            end = finding.get("line_end")
            if start:
                location = f"lines {start}-{end or start}"
        return f"{file_path} ({location})" if location else file_path

    @staticmethod
    def _draw_cover_background(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(WHITE)
        canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        canvas.setFillColor(INK_2)
        canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, fill=1, stroke=0)
        canvas.setFillColor(CYAN_DARK)
        canvas.rect(0, PAGE_HEIGHT - 9.5 * mm, 42 * mm, 1.5 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(SLATE_200)
        canvas.setLineWidth(0.7)
        canvas.line(LEFT_MARGIN, 18 * mm, PAGE_WIDTH - RIGHT_MARGIN, 18 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE_500)
        canvas.drawString(LEFT_MARGIN, 13 * mm, "Generated locally - customer review copy")
        canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 13 * mm, "clausi.ai")
        canvas.restoreState()
