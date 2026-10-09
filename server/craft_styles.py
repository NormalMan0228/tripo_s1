"""Named craft styles and sizes the player picks in the craft window.

The client only sends an id; the wording sent to the LLM designer, the concept picture and
Tripo lives here, so it can be tuned (or a style added) on the server without a game update.
/v1/studio lists them with Korean, English and Chinese names for the window.
"""

STYLES = [
    {'id': 'rpg',
     'names': {'ko': '판타지 RPG', 'en': 'Fantasy RPG', 'zh': '奇幻 RPG'},
     'hints': {'ko': '실제 같은 재질과 비율의 고급 게임 소품', 'en': 'High-quality game props with real materials and proportions', 'zh': '材质与比例逼真的高品质游戏道具'},
     'llm': ('a high-quality semi-realistic game prop from a modern fantasy RPG: believable real-world proportions and '
             'construction, real materials (wood grain, forged metal, woven fabric, stone, glass, ceramic), refined '
             'craftsmanship and purposeful detail, a natural warm palette. Avoid toy-like, chibi or cartoon proportions, '
             'blobby shapes and candy colours'),
     'concept': ('high-quality semi-realistic game asset like a modern fantasy RPG prop: believable real-world proportions '
                 'and construction, real material detail (wood grain, metal, fabric, stone, glass), refined craftsmanship. '
                 'Not cartoonish, not toy-like, not chibi'),
     'prop': 'high-quality semi-realistic fantasy RPG game prop with believable proportions and real materials, not toy-like'},
    {'id': 'cozy',
     'names': {'ko': '아늑한 동화', 'en': 'Cozy storybook', 'zh': '温馨童话'},
     'hints': {'ko': '둥글고 따뜻한 동화 같은 느낌', 'en': 'Soft, rounded and warm like a picture book', 'zh': '圆润温暖的童话感'},
     'llm': ('a cozy illustrated storybook prop: soft rounded silhouettes, friendly shapes, warm ivory, honey wood, sage '
             'green and muted coral, brushed matte surfaces'),
     'concept': 'soft illustrated cozy storybook game style, rounded friendly shapes, warm muted palette, matte surfaces',
     'prop': 'cozy storybook-style game prop with soft rounded shapes and warm muted colours'},
    {'id': 'realistic',
     'names': {'ko': '실사', 'en': 'Photoreal', 'zh': '写实'},
     'hints': {'ko': '실제 제품 사진 같은 사실적인 가구', 'en': 'Looks like a real product photo', 'zh': '像真实产品照片一样'},
     'llm': ('a photorealistic real-world object exactly like a real product: accurate dimensions, real manufacturing '
             'details, physically accurate materials and subtle wear. No stylisation'),
     'concept': 'photorealistic studio product photograph, accurate real materials and dimensions, subtle realistic wear',
     'prop': 'photorealistic real-world object with accurate proportions, construction and materials'},
    {'id': 'anime',
     'names': {'ko': '애니메이션', 'en': 'Anime', 'zh': '动漫'},
     'hints': {'ko': '선명한 색과 깔끔한 셀 셰이딩', 'en': 'Bright colours and clean cel shading', 'zh': '鲜明色彩与干净的赛璐璐着色'},
     'llm': ('an anime cel-shaded game prop like a modern anime RPG: clean confident shapes, crisp silhouette, flat '
             'bright colour areas with simple two-tone shading, tidy details, believable proportions (not chibi)'),
     'concept': 'anime cel-shaded game art like a modern anime RPG prop, clean lines, flat bright colours with crisp two-tone shading, not chibi',
     'prop': 'anime cel-shaded game prop with clean shapes and flat bright colours, believable proportions'},
    {'id': 'antique',
     'names': {'ko': '앤티크', 'en': 'Antique', 'zh': '古典'},
     'hints': {'ko': '섬세한 조각과 황동 장식의 고풍스러운 유럽 가구', 'en': 'Ornate European antique with carving and brass', 'zh': '雕花与黄铜装饰的欧式古董'},
     'llm': ('a European antique / Victorian piece: dark polished hardwood, ornate hand carving, turned legs, brass or gilt '
             'fittings, velvet or leather upholstery, aged patina'),
     'concept': 'European antique Victorian craftsmanship, dark polished hardwood, ornate carving, brass fittings, aged patina',
     'prop': 'European antique Victorian piece with dark polished wood, ornate carving and brass fittings'},
    {'id': 'hanok',
     'names': {'ko': '한옥 전통', 'en': 'Korean traditional', 'zh': '韩屋传统'},
     'hints': {'ko': '나뭇결, 자개, 한지가 어우러진 한국 전통 가구', 'en': 'Korean wood, mother-of-pearl and hanji paper', 'zh': '木纹、螺钿与韩纸的韩国传统家具'},
     'llm': ('Korean traditional (Joseon, hanok) craftsmanship: natural pine or zelkova wood with visible grain, brass hinges '
             'and corner fittings, mother-of-pearl (najeon) inlay, hanji paper, ottchil lacquer, restrained elegant lines'),
     'concept': 'Korean traditional Joseon hanok furniture, natural wood grain, brass fittings, mother-of-pearl inlay, hanji paper, elegant restrained lines',
     'prop': 'Korean traditional Joseon-style piece with natural wood grain, brass fittings and mother-of-pearl inlay'},
    {'id': 'scifi',
     'names': {'ko': '미래 SF', 'en': 'Sci-fi', 'zh': '科幻'},
     'hints': {'ko': '매끈한 금속과 빛나는 장식의 미래형 가구', 'en': 'Sleek metal with glowing accents', 'zh': '光滑金属与发光装饰的未来家具'},
     'llm': ('a sleek near-future sci-fi design: brushed metal, white composite panels, glass, precise panel seams, subtle '
             'glowing accent strips, functional tech details'),
     'concept': 'sleek near-future sci-fi design, brushed metal and white composite panels, precise seams, subtle glowing accent lights',
     'prop': 'sleek near-future sci-fi piece with brushed metal, composite panels and glowing accents'},
    {'id': 'lowpoly',
     'names': {'ko': '로우폴리', 'en': 'Low-poly', 'zh': '低多边形'},
     'hints': {'ko': '각진 면과 단순한 색의 미니멀 스타일', 'en': 'Faceted shapes and simple flat colours', 'zh': '棱角分明、配色简洁的极简风格'},
     'llm': ('low-poly faceted game art: a few large flat-shaded planar facets, clean geometric silhouette, a limited flat '
             'colour palette, no fine texture detail'),
     'concept': 'low-poly faceted 3D game art, large flat-shaded facets, clean geometric silhouette, limited flat colour palette',
     'prop': 'low-poly faceted game prop with flat-shaded facets and a limited flat colour palette'},
    {'id': 'nature',
     'names': {'ko': '숲속 자연', 'en': 'Woodland', 'zh': '森林自然'},
     'hints': {'ko': '통나무, 이끼, 돌로 만든 자연스러운 가구', 'en': 'Logs, moss and stone, hand-made', 'zh': '原木、苔藓与石头打造的自然家具'},
     'llm': ('rustic woodland craft: raw logs and branches with bark, moss, river stone, woven vines, hand-made organic shapes, '
             'earthy natural colours'),
     'concept': 'rustic woodland handcraft, raw logs and branches with bark, moss, river stone, woven vines, earthy natural colours',
     'prop': 'rustic woodland hand-made piece of logs, branches, moss and stone'},
]
STYLE_IDS = tuple(s['id'] for s in STYLES)
DEFAULT_STYLE = 'rpg'

# Longest side in metres; 'auto' keeps the designer's real-world sizes.
SIZES = [
    {'id': 'auto', 'meters': 0, 'names': {'ko': '자동', 'en': 'Auto', 'zh': '自动'}},
    {'id': 'small', 'meters': .6, 'names': {'ko': '작게', 'en': 'Small', 'zh': '小'}},
    {'id': 'medium', 'meters': 1.2, 'names': {'ko': '보통', 'en': 'Medium', 'zh': '中'}},
    {'id': 'large', 'meters': 1.8, 'names': {'ko': '크게', 'en': 'Large', 'zh': '大'}},
    {'id': 'huge', 'meters': 2.4, 'names': {'ko': '아주 크게', 'en': 'Extra large', 'zh': '特大'}},
]
SIZE_IDS = tuple(s['id'] for s in SIZES)


def style(style_id):
    return next((s for s in STYLES if s['id'] == style_id), STYLES[0])


def meters(size_id):
    return next((s['meters'] for s in SIZES if s['id'] == size_id), 0)


def designer_style(style_id, size_id):
    """The STYLE section of the LLM designer prompt (trusted server text)."""
    text = ('Villagen: a sunny island village in a modern fantasy RPG. Unless the player asks for another style, describe '
            'each object as ' + style(style_id)['llm'] + '. Readable at an orthographic camera distance. Avoid horror, '
            'realistic skin and razor edges.')
    size = meters(size_id)
    if size:
        return text + f' The finished object is about {size:g} m on its longest side: scale every part, its proportions and detail for that size.'
    return text + ' Use believable real-world dimensions in metres for every part.'


def public():
    return {'styles': [{k: s[k] for k in ('id', 'names', 'hints')} for s in STYLES],
            'sizes': [{'id': s['id'], 'meters': s['meters'], 'names': s['names']} for s in SIZES],
            'default_style': DEFAULT_STYLE}
