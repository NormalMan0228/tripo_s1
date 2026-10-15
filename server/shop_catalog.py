"""NPC shop data. Existing harvest prices and seed prices have one source of truth."""
from . import homestead


def bag_item(item, coins, daily=None):
    return {'name': homestead.NAMES[item], 'coins': coins, 'shards': 0,
            'kind': 'bag', 'daily_limit': daily}


# No new daily cap on the legacy seeds, bait or harvest sales.
SEEDS = {item: bag_item(item, price) for item, price in homestead.SHOP.items()}
HARVEST = {item: {'coins': price, 'shards': 0, 'daily_limit': None}
           for item, price in homestead.PRICES.items()}
DECORATIONS = {
    'flower_pot': {'title': '작은 화분', 'category': 'plant', 'parts': [
        ('pot', 'ellipsoid', [.3, .25, .3], [0, .125, 0], '#c9783f'),
        ('leaves', 'ellipsoid', [.35, .35, .35], [0, .4, 0], '#6f9a4f')]},
    'table_lamp': {'title': '작은 탁상등', 'category': 'lamp', 'parts': [
        ('base', 'box', [.25, .05, .25], [0, .025, 0], '#8b6a48'),
        ('stem', 'box', [.04, .3, .04], [0, .2, 0], '#8b6a48'),
        ('shade', 'ellipsoid', [.32, .2, .32], [0, .4, 0], '#f2ead8')]},
}
SHOPS = {
    'general_store': {
        'name': '단비의 잡화점', 'npc': 'shopkeeper', 'building': '13_shop',
        'required_flag': 'danbi_moved_in',
        'buy': {**SEEDS, **{item: {'name': preset['title'], 'coins': 20, 'shards': 0,
                                 'kind': 'decoration', 'daily_limit': 1, 'rotation': i}
                           for i, (item, preset) in enumerate(DECORATIONS.items())}},
        'rotation_days': 2, 'sell': HARVEST, 'services': {},
    },
    'farm_stall': {
        'name': '한결의 씨앗 가게', 'npc': 'farmer', 'building': '03_teal_cottage',
        'buy': SEEDS, 'sell': HARVEST,
        'services': {'daily_order': {'name': '마을 식탁 배달', 'kind': 'order',
                                   'items': {'turnip': 2, 'perch': 1}, 'coins_reward': 20,
                                   'daily_limit': 1}},
    },
    'cafe': {
        'name': '빨간 지붕', 'npc': 'regular', 'building': '01_cafe', 'buy': {}, 'sell': {},
        'services': {'herb_tea': {'name': '따뜻한 허브차', 'kind': 'mood', 'coins': 3,
                                 'shards': 0, 'mood': 'cozy', 'seconds': 600, 'daily_limit': 3}},
    },
    'fishing_shack': {
        'name': '보람의 생선 매입', 'npc': 'fisher', 'building': '17_lighthouse',
        'buy': {'bait': SEEDS['bait']},
        'sell': {item: HARVEST[item] for item in homestead.FISH},
        'services': {'sell_fish': {'name': '잡은 생선 팔기', 'kind': 'sell'}},
    },
}
