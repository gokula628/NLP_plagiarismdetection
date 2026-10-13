import os
import io
import zipfile
import xml.etree.ElementTree as ET
from flask import (
    Flask,
    render_template,
    request,
    send_file
)

from PyPDF2 import PdfReader

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.enums import TA_CENTER

from plagiarism_detector import (
    calculate_similarity,
    find_matching_sentences,
    generate_highlighted_texts,
    analyze_zip_batch
)

app = Flask(__name__)
app.secret_key = "nlp_plagiarism_secret_key"

UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

latest_analysis = {}


# ==========================================================
# BULLETPROOF TEXT EXTRACTION (PDF & DOCX)
# ==========================================================

def extract_text_from_file(file):
    filename = file.filename.lower() if hasattr(file, 'filename') else getattr(file, 'name', '').lower()

    if filename.endswith(".pdf"):
        try:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            print("PDF reading error:", e)
            return ""

    elif filename.endswith(".docx"):
        try:
            from docx import Document
            document = Document(file)
            text = ""
            for paragraph in document.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text
        except Exception:
            try:
                with zipfile.ZipFile(file) as z:
                    xml_content = z.read('word/document.xml')
                    tree = ET.fromstring(xml_content)
                    paragraphs = []
                    for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                        texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                        if texts:
                            paragraphs.append("".join(texts))
                    return "\n".join(paragraphs)
            except Exception as ex:
                print("DOCX fallback error:", ex)
                return ""

    return ""


def extract_texts_from_zip(zip_file):
    file_dict = {}
    try:
        with zipfile.ZipFile(zip_file) as z:
            for name in z.namelist():
                if name.startswith('__MACOSX') or name.endswith('/') or name.startswith('.'):
                    continue
                lower_name = name.lower()
                if lower_name.endswith('.pdf') or lower_name.endswith('.docx'):
                    content = z.read(name)
                    file_obj = io.BytesIO(content)
                    file_obj.filename = os.path.basename(name)
                    extracted_text = extract_text_from_file(file_obj)
                    if extracted_text.strip():
                        file_dict[os.path.basename(name)] = extracted_text
    except Exception as e:
        print("Zip extraction error:", e)
    return file_dict


def classify_similarity(score):
    if score >= 70:
        return "High Plagiarism Risk"
    elif score >= 40:
        return "Moderate Plagiarism Risk"
    else:
        return "Low / Original Content"


# ==========================================================
# REPORT GENERATION (PDF)
# ==========================================================

def generate_report(data):
    report_path = os.path.join(REPORT_FOLDER, "plagiarism_report.pdf")
    document = SimpleDocTemplate(
        report_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=15,
        textColor=colors.HexColor("#18243a")
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#23458f")
    )
    normal_style = ParagraphStyle(
        "NormalText",
        parent=styles["BodyText"],
        fontSize=9,
        leading=14
    )

    story = []

    story.append(Paragraph("Academic Plagiarism Analysis Report", title_style))
    story.append(Paragraph("NLP-Based Academic Plagiarism Detection System", normal_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph("Analysis Overview", heading_style))

    summary_data = [
        ["Metric", "Score / Details"],
        ["Analysis Mode", data.get("mode", "Dual Document Comparison")],
        ["Plagiarism Similarity Score", f"{data.get('similarity', 0)}%"],
        ["Classification Result", data.get("result", "N/A")]
    ]

    summary_table = Table(summary_data, colWidths=[220, 210])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2ff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#23458f")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7e2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))
    story.append(summary_table)

    story.append(Paragraph("NLP Methodology", heading_style))
    story.append(Paragraph("This system uses TF-IDF N-gram vectorization and cosine similarity for efficient and accurate text plagiarism detection.", normal_style))

    document.build(story)
    return report_path


# ==========================================================
# MAIN ROUTE
# ==========================================================

@app.route("/", methods=["GET", "POST"])
def home():
    global latest_analysis

    active_tab = "dual"
    similarity = None
    result = None
    error = None
    html1, html2 = "", ""
    batch_result = None

    if request.method == "POST":
        mode = request.form.get("mode", "dual")
        active_tab = mode

        # ======================================================
        # MODE 1: DUAL DOCUMENT COMPARISON
        # ======================================================
        if mode == "dual":
            file1 = request.files.get("file1")
            file2 = request.files.get("file2")

            if not file1 or not file2 or file1.filename == "" or file2.filename == "":
                error = "Please upload both documents for comparison."
            else:
                ext1 = os.path.splitext(file1.filename)[1].lower()
                ext2 = os.path.splitext(file2.filename)[1].lower()

                if ext1 not in [".pdf", ".docx"] or ext2 not in [".pdf", ".docx"]:
                    error = "Only PDF and DOCX file formats are supported."
                else:
                    text1 = extract_text_from_file(file1)
                    text2 = extract_text_from_file(file2)

                    if not text1.strip() or not text2.strip():
                        error = "Could not extract text content from one or both files."
                    else:
                        similarity = calculate_similarity(text1, text2)
                        result = classify_similarity(similarity)

                        matching_sentences = find_matching_sentences(text1, text2)
                        html1, html2 = generate_highlighted_texts(text1, text2, matching_sentences)

                        latest_analysis = {
                            "mode": "Dual Document Check",
                            "similarity": similarity,
                            "result": result,
                            "doc1_name": file1.filename,
                            "doc2_name": file2.filename
                        }

                        try:
                            generate_report(latest_analysis)
                        except Exception as e:
                            print("Report pre-generation error:", e)

        # ======================================================
        # MODE 2: CLASS-WIDE BATCH ZIP ANALYSIS
        # ======================================================
        elif mode == "batch":
            zip_file = request.files.get("zip_file")
            if not zip_file or not zip_file.filename.lower().endswith(".zip"):
                error = "Please upload a valid .zip file containing student PDF/DOCX assignments."
            else:
                file_dict = extract_texts_from_zip(zip_file)
                if len(file_dict) < 2:
                    error = "Extracted fewer than 2 valid PDF/DOCX files from the zip archive."
                else:
                    batch_result = analyze_zip_batch(file_dict)
                    overall_avg = batch_result.get("overall_average_similarity", 0.0)
                    batch_status = classify_similarity(overall_avg)

                    latest_analysis = {
                        "mode": "Class-Wide Batch Check",
                        "similarity": overall_avg,
                        "result": f"Class Average: {batch_status}"
                    }
                    try:
                        generate_report(latest_analysis)
                    except Exception as e:
                        print("Report pre-generation error:", e)

    return render_template(
        "index.html",
        active_tab=active_tab,
        similarity=similarity,
        result=result,
        error=error,
        html1=html1,
        html2=html2,
        batch_result=batch_result
    )


@app.route("/download-report")
def download_report():
    report_path = os.path.join(REPORT_FOLDER, "plagiarism_report.pdf")

    if os.path.exists(report_path):
        return send_file(
            os.path.abspath(report_path),
            as_attachment=True,
            download_name="Plagiarism_Report.pdf"
        )

    if latest_analysis:
        try:
            path = generate_report(latest_analysis)
            return send_file(
                os.path.abspath(path),
                as_attachment=True,
                download_name="Plagiarism_Report.pdf"
            )
        except Exception as e:
            return f"Error generating PDF report: {e}", 500

    return "Please perform an analysis first before downloading report.", 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)