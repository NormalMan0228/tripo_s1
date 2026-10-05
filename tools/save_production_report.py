"""Save the reviewed local report as a Korean PDF and an offline media package.

Run with the Codex bundled Python, which supplies ReportLab, lxml and Pillow.
No provider API calls, browser automation, or credentials are involved.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import re
import shutil
import zipfile

from lxml import html
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Image, Table, TableStyle, Spacer,
    KeepTogether, PageBreak, Flowable, CondPageBreak,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'artifacts/production-lab-20261003/review'
OUTPUT = ROOT / 'output/pdf'
OUTPUT.mkdir(parents=True, exist_ok=True)
PDF = OUTPUT / 'Tripothon_Production_Report_20261003.pdf'
ZIP = OUTPUT / 'Tripothon_Report_With_Videos_20261003.zip'
tree = html.fromstring((REVIEW / 'index.html').read_text(encoding='utf-8'))

pdfmetrics.registerFont(TTFont('Korean', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoreanBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='KoreanBold')
WIDTH = letter[0] - 108
styles = {
    'body': ParagraphStyle('body', fontName='Korean', fontSize=11, leading=17,
                           wordWrap='CJK', spaceAfter=9, textColor=colors.HexColor('#25332F')),
    'title': ParagraphStyle('title', fontName='KoreanBold', fontSize=27, leading=36,
                            wordWrap='CJK', spaceAfter=17, textColor=colors.black),
    'h1': ParagraphStyle('h1', fontName='KoreanBold', fontSize=19, leading=27,
                         spaceBefore=15, spaceAfter=12, keepWithNext=True,
                         wordWrap='CJK', textColor=colors.black),
    'h2': ParagraphStyle('h2', fontName='KoreanBold', fontSize=13, leading=19,
                         spaceBefore=12, spaceAfter=7, keepWithNext=True,
                         wordWrap='CJK', textColor=colors.black),
    'small': ParagraphStyle('small', fontName='Korean', fontSize=9, leading=14,
                            spaceAfter=8, wordWrap='CJK', textColor=colors.HexColor('#51625C')),
    'caption': ParagraphStyle('caption', fontName='Korean', fontSize=9, leading=14,
                              spaceAfter=12, wordWrap='CJK', textColor=colors.HexColor('#51625C')),
    'cell': ParagraphStyle('cell', fontName='Korean', fontSize=9.5, leading=14.2,
                           wordWrap='CJK', textColor=colors.HexColor('#25332F')),
    'header': ParagraphStyle('header', fontName='KoreanBold', fontSize=10, leading=15,
                             wordWrap='CJK', textColor=colors.white),
    'code': ParagraphStyle('code', fontName='Korean', fontSize=9, leading=14,
                           wordWrap='CJK', spaceAfter=10),
}


def clean(text):
    return re.sub(r'\s+', ' ', text or '').strip().replace('↗', '').strip()


def inline(element):
    result = escape(clean(element.text))
    for child in element:
        tag = child.tag if isinstance(child.tag, str) else ''
        value = inline(child)
        if tag == 'a':
            target = child.get('href', '')
            if target in ('explorer_b.glb', 'explorer_b_reusable.blend'):
                result += value + ' (프로젝트 원본)'
            elif target.startswith('https://'):
                result += f'<link href="{escape(target)}" color="#267365">{value}</link>'
            elif target and not target.startswith('#'):
                result += f'<link href="{escape(target)}" color="#267365">{value}</link>'
            else:
                result += value
        elif tag in ('b', 'strong'):
            result += '<b>' + value + '</b>'
        elif tag == 'br':
            result += '<br/>'
        elif tag == 'small':
            result += '<br/><font size="8.5">' + value + '</font>'
        else:
            result += value
        if child.tail:
            result += ' ' + escape(clean(child.tail))
    return result


def p(text, style='body'):
    return Paragraph(text, styles[style])


def figure(file, caption, width=WIDTH, max_height=230, heading=None):
    path = REVIEW / file
    with PILImage.open(path) as image:
        w, h = image.size
    scale = min(width / w, max_height / h)
    img = Image(str(path), width=w * scale, height=h * scale)
    img.hAlign = 'CENTER'
    content = [img, Spacer(1, 6), p(escape(caption), 'caption')]
    if heading:
        content.insert(0, p(escape(heading), 'h2'))
    return KeepTogether(content)


class PairedFigures(Flowable):
    """Place related reference images together without shrinking body text."""
    def __init__(self, files):
        super().__init__()
        self.files = files
        self.width = WIDTH
        self.height = 168

    def draw(self):
        column = (WIDTH - 14) / 2
        for index, file in enumerate(self.files):
            path = REVIEW / file
            with PILImage.open(path) as img:
                w, h = img.size
            scale = min(column / w, self.height / h)
            self.canv.drawImage(str(path), index * (column + 14) + (column - w * scale) / 2,
                                (self.height - h * scale) / 2, width=w * scale, height=h * scale)


def table(element, section):
    rows = element.xpath('.//tr')
    cols = len(rows[0].xpath('./th|./td'))
    if cols == 4:
        widths = [40, 117, 116, WIDTH - 273]
    elif section == 'cost':
        widths = [146, 51, WIDTH - 197]
    elif section == 'next':
        widths = [100, 150, WIDTH - 250]
    else:
        widths = [105, 146, WIDTH - 251]
    data = []
    for index, row in enumerate(rows):
        cells = row.xpath('./th|./td')
        data.append([p(inline(cell), 'header' if index == 0 else 'cell') for cell in cells])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#304C57')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F6F7')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D9D9D9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return [t, Spacer(1, 13)]


def blocks(element, section):
    result = []
    for node in element:
        tag = node.tag if isinstance(node.tag, str) else ''
        cls = node.get('class', '').split()
        if 'controls' in cls or tag in ('script', 'style', 'source', 'input', 'output', 'button'):
            continue
        if tag == 'h2':
            continue
        if tag in ('h3', 'summary'):
            if tag == 'h3' and section == 'motion' and 'card' in element.get('class', '').split():
                continue
            title = clean(' '.join(node.itertext()))
            title = re.sub(r'[·:/.→↗]+', ' ', title)
            result.append(p(escape(title), 'h2'))
        elif tag in ('p', 'small', 'pre'):
            text = inline(node)
            if tag == 'pre':
                text = escape(node.text_content()).replace('\n', '<br/>')
            if text:
                result.append(p(text, 'code' if tag == 'pre' else 'small' if tag == 'small' or 'tag' in cls else 'body'))
        elif tag == 'table':
            result.extend(table(node, section))
        elif tag == 'img':
            result.append(figure(node.get('src'), node.get('alt', '실제 결과 이미지')))
        elif tag == 'video':
            stem = node.get('id')
            if stem:
                heading = clean(node.getparent().xpath('./h3')[0].text_content()).replace('·', ' ')
                result.append(figure(stem + '-poster.jpg',
                    '실제 Godot 녹화의 한 프레임이며 생성 영상이 아닙니다', heading=heading))
                result.append(p(f'영상 파일 <link href="{stem}-browser.mp4" color="#267365">{stem}-browser.mp4</link>'
                                f' · <link href="{stem}-browser.webm" color="#267365">WebM 대체 형식</link>', 'small'))
            # The video-model section uses a shared contact sheet instead.
        elif tag == 'div' and 'gallery' in cls:
            files = [image.get('src') for image in node.xpath('.//img')]
            result.append(KeepTogether([PairedFigures(files), Spacer(1, 6),
                p('실제 Godot 화면의 전신과 손 소매 연결부 확대입니다. 새 몸체는 별도 손 메시를 이어 붙이지 않았으며, '
                  '새 리그에는 손가락 개별 뼈가 없습니다.', 'caption')]))
        elif 'tag' in cls:
            result.append(p(inline(node), 'small'))
        elif 'metric' in cls:
            value = clean(node.text_content())
            if value:
                result.append(p('<b>' + escape(value) + '</b>'))
        elif tag == 'div' and 'flow' in cls:
            for number, step in enumerate(node, 1):
                head = step.xpath('./b')
                if head:
                    result.append(p(f'{number} {escape(clean(head[0].text_content()))}', 'h2'))
                for para in step.xpath('./p'):
                    result.append(p(inline(para)))
        else:
            result.extend(blocks(node, section))
    return result


def page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFont('Korean', 8)
    canvas.setFillColor(colors.black)
    canvas.drawString(54, letter[1] - 32, 'Tripothon 제작 파이프라인 검증')
    canvas.setFillColor(colors.HexColor('#66756E'))
    canvas.drawString(54, 30, '2026년 10월 3일  |  개발 검수 기록')
    canvas.drawRightString(letter[0] - 54, 30, str(doc.page))
    canvas.restoreState()


story = [
    p('Tripothon 제작 파이프라인<br/>검증 보고서', 'title'),
    p('2026년 10월 3일', 'small'),
    p('Stefan 강의와 Mr Mak 자료를 Godot 제작 흐름에 적용한 결과를 기록했습니다. '
      '영상 모델 3종 비교와 Tripo 캐릭터 제작, 리깅과 보행 보정, 실제 게임 속도와 전환 검사, '
      '서비스 비용과 상업 이용 조건을 함께 정리했습니다.'),
    p('새 B형 탐험가와 기존 게임 캐릭터는 구분하여 검수했습니다. 대기와 걷기와 달리기의 검사 표본은 통과했으며, '
      '새 리그의 손가락과 표정 및 모든 행동 전환의 완성은 다음 작업으로 남아 있습니다.'),
    p('이 PDF는 이미지와 검사 결과를 보관하는 문서입니다. 영상은 함께 저장한 index.html에서 재생하거나 '
      'MP4 및 WebM 파일을 직접 열어 확인할 수 있습니다. 오프라인 묶음의 파일 위치를 유지해야 영상 링크가 작동합니다.', 'small'),
    p('<link href="index.html#motion" color="#267365">실제 애니메이션 적용 영상 열기</link>', 'small'),
]
story.append(p('보고서 구성', 'h2'))
for number, section in enumerate(tree.xpath('//main/section'), 1):
    heading = clean(section.xpath('./h2')[0].text_content())
    story.append(p(f'<link href="#section-{number}" color="#267365">{number} {escape(heading)}</link>', 'small'))

for number, section in enumerate(tree.xpath('//main/section'), 1):
    sid = section.get('id')
    if number == 1:
        story.append(PageBreak())
    else:
        story.append(CondPageBreak(160))
    title = clean(section.xpath('./h2')[0].text_content())
    title = re.sub(r'[·:/.→↗]+', ' ', title)
    story.append(p(f'<a name="section-{number}"/>{number} {escape(title)}', 'h1'))
    if sid == 'video':
        story.append(figure('video-comparison.jpg', '같은 레퍼런스를 사용한 영상 3종의 실제 출력 비교', max_height=200))
    story.extend(blocks(section, sid))
    if sid == 'cost':
        story.append(p('고정 계산 예시', 'h2'))
        story.append(p('입력 3,000토큰과 출력 600토큰을 가정하면 요청 1회는 32.16 neurons입니다. '
            '1,000회는 $0.35376 상당이며, 일일 무료 10,000 neurons를 적용한 1,000회 요청의 추론 비용은 약 $0.244입니다. '
            'HTML의 요청 수 조절 기능은 PDF에서 이 고정 예시로 저장했습니다.'))

story.append(p('영상 재생 보완 기록', 'h2'))
story.append(p('2026년 10월 3일 기존 H264 영상은 파일 디코딩 검사에서 정상이나, 인앱 브라우저에서는 '
               '재생 시간이 진행되어도 화면이 비어 보였습니다. WebM을 기본 재생 형식으로 추가하고 '
               'H264 Baseline MP4도 별도로 저장했습니다. 두 실제 Godot 영상의 화면과 시간 진행을 확인했으며, '
               '보고서 서버에는 부분 다운로드와 탐색을 위한 HTTP Range 지원을 추가했습니다.'))
footer = tree.xpath('//footer')
if footer:
    story.append(p(inline(footer[0]), 'small'))

doc = SimpleDocTemplate(str(PDF), pagesize=letter, rightMargin=54, leftMargin=54,
                        topMargin=54, bottomMargin=48, title='Tripothon 제작 파이프라인 검증 보고서',
                        author='Tripothon', pageCompression=1)
doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
shutil.copy2(PDF, REVIEW / PDF.name)

# The offline package contains the report, videos, images and audit data.
# Large source art is already available in the project and is not bundled twice.
offline_html = (REVIEW / 'index.html').read_text(encoding='utf-8')
offline_html = offline_html.replace('<a download href="explorer_b.glb">재사용 가능한 GLB 받기</a> · <a download href="explorer_b_reusable.blend">Blender 원본 받기</a> · ',
                                  'GLB와 Blender 제작 원본은 프로젝트 결과 폴더에서 확인할 수 있습니다. · ')
offline_html = offline_html.replace('<a style="color:#faf4df" href="Tripothon_Report_With_Videos_20261003.zip" download>영상 포함 오프라인 문서 저장</a>', '')
extensions = {'.png', '.jpg', '.mp4', '.webm', '.json'}
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('Tripothon_Report_20261003/index.html', offline_html)
    archive.write(PDF, 'Tripothon_Report_20261003/' + PDF.name)
    for file in sorted(REVIEW.iterdir()):
        if file.suffix in extensions:
            archive.write(file, 'Tripothon_Report_20261003/' + file.name)
    archive.writestr('Tripothon_Report_20261003/먼저 읽어주세요.txt',
        '압축을 모두 풀고 index.html을 브라우저에서 열어주세요.\n'
        '실제 게임 영상은 속도·연속성 메뉴에서 재생합니다.\n'
        'PDF는 영상의 대표 프레임과 검사 결과를 보관합니다. 영상은 HTML 또는 MP4/WebM으로 재생합니다.\n'
        '하위 파일들을 이동하면 문서의 영상 링크가 끊길 수 있습니다.\n'
        'GLB와 Blender 원본은 원래 프로젝트 결과 폴더에 보존되어 있습니다.\n')
shutil.copy2(ZIP, REVIEW / ZIP.name)
print('PDF_SAVED', PDF)
print('OFFLINE_PACKAGE_SAVED', ZIP)
