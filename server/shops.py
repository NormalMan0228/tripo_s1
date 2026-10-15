"""Account-owned NPC trading, sharing the homestead inventory and sale reward cap."""
import json
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation
from . import economy, homestead, npc_homes, story
from .shop_catalog import SHOPS, DECORATIONS

SCHEMA = '''
CREATE TABLE IF NOT EXISTS shop_usage (
 user_id TEXT NOT NULL REFERENCES users(id), shop_id TEXT NOT NULL,
 action TEXT NOT NULL, item TEXT NOT NULL, day INTEGER NOT NULL, quantity INTEGER NOT NULL,
 PRIMARY KEY(user_id,shop_id,action,item,day));
'''


class Trade(Mutation):
    version: int = Field(ge=0, strict=True)
    item: str = Field(min_length=1, max_length=24, pattern=r'^[a-z_]+$')
    quantity: int = Field(default=1, ge=1, le=20, strict=True)


class Service(Mutation):
    version: int = Field(ge=0, strict=True)
    service: str = Field(min_length=1, max_length=24, pattern=r'^[a-z_]+$')
    item: str = Field(default='', max_length=24, pattern=r'^[a-z_]*$')
    quantity: int = Field(default=1, ge=1, le=20, strict=True)


def fail(code, status=409):
    raise HTTPException(status, code)


def definition(shop_id):
    if shop_id not in SHOPS:
        fail('shop_not_found', 404)
    return SHOPS[shop_id]


def life_state(conn, user_id):
    row = conn.execute('SELECT state FROM homesteads WHERE user_id=?', (user_id,)).fetchone()
    return homestead.normalise(json.loads(row['state'])) if row else homestead.initial()


def save(conn, user_id, state):
    conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                 (user_id, json.dumps(state)))


def is_open(conn, user_id, shop):
    flag = shop.get('required_flag')
    return not flag or story.has_flag(conn, user_id, flag)


def offered(shop, item, day):
    return 'rotation' not in item or item['rotation'] == day % shop['rotation_days']


def used(conn, user_id, shop_id, action, item, day):
    row = conn.execute('SELECT quantity FROM shop_usage WHERE user_id=? AND shop_id=? AND action=? AND item=? AND day=?',
                       (user_id, shop_id, action, item, day)).fetchone()
    return row[0] if row else 0


def reserve(conn, user_id, shop_id, action, item, spec, day, quantity):
    cap = spec.get('daily_limit')
    if cap is None:
        return
    if used(conn, user_id, shop_id, action, item, day) + quantity > cap:
        fail('shop_daily_limit')
    conn.execute('INSERT INTO shop_usage VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,shop_id,action,item,day) '
                 'DO UPDATE SET quantity=quantity+excluded.quantity', (user_id, shop_id, action, item, day, quantity))


class Shops:
    def __init__(self, app, db, settings, clock, auth, mutate, money, assets):
        self.db, self.settings, self.clock = db, settings, clock
        self.money, self.assets = money, assets
        with db.read() as conn:
            conn.executescript(SCHEMA)

        @app.get('/v1/shops/{shop_id}')
        def read(shop_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                return self.public(conn, user['id'], shop_id)

        @app.post('/v1/shops/{shop_id}/buy')
        def buy(shop_id: str, body: Trade, request: Request):
            return mutate(request, body, 'shop:' + shop_id + ':buy',
                          lambda conn, user: self.trade(conn, user, shop_id, 'buy', body))

        @app.post('/v1/shops/{shop_id}/sell')
        def sell(shop_id: str, body: Trade, request: Request):
            return mutate(request, body, 'shop:' + shop_id + ':sell',
                          lambda conn, user: self.trade(conn, user, shop_id, 'sell', body))

        @app.post('/v1/shops/{shop_id}/service')
        def service(shop_id: str, body: Service, request: Request):
            return mutate(request, body, 'shop:' + shop_id + ':service',
                          lambda conn, user: self.service(conn, user, shop_id, body))

    def public(self, conn, user_id, shop_id):
        shop = definition(shop_id)
        now = self.clock()
        day = homestead.local_day(now)
        state = life_state(conn, user_id)
        entries = {}
        for action, field in (('buy', 'buy'), ('sell', 'sell'), ('service', 'services')):
            entries[field] = []
            for item, spec in shop[field].items():
                if not offered(shop, spec, day):
                    continue
                cap = spec.get('daily_limit')
                remaining = None if cap is None else max(0, cap - used(conn, user_id, shop_id, action, item, day))
                if spec.get('kind') == 'order':
                    remaining = int(state['order_day'] != day)
                entries[field].append({'id': item, 'name': homestead.NAMES.get(item, item), **spec,
                                       'remaining': remaining})
        opened = is_open(conn, user_id, shop)
        offset = homestead.DAILY_OFFSET.get()
        offset = homestead.UTC_OFFSET.get() if offset is None else offset
        return {'id': shop_id, 'name': shop['name'], 'npc': shop['npc'], 'building': shop['building'],
                'open': bool(opened), 'closed_reason': None if opened else 'danbi_not_moved_in',
                'required_flag': shop.get('required_flag'), 'server_time': now, 'day': day,
                'resets_at': (day + 1) * 86400 - offset * 60, 'stock_scope': 'account',
                'version': state['version'], 'coins': state['coins'],
                'shards': conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()[0],
                'sell_stars': homestead.star_status(state, now, self.settings.sell_stars_daily, self.settings.sell_coins_per_star),
                'effects': self.effects(state, now), **entries}

    @staticmethod
    def effects(state, now):
        return {key: effect for key, effect in state.get('shop_effects', {}).items() if effect['expires_at'] > now}

    def prepare(self, conn, user, shop_id, body):
        shop = definition(shop_id)
        if not is_open(conn, user['id'], shop):
            fail('shop_closed')
        state = life_state(conn, user['id'])
        if state['version'] != body.version:
            fail('stale_life_version')
        return shop, state, self.clock()

    def finish(self, conn, user, state, now, message, **extra):
        state['version'] += 1
        save(conn, user['id'], state)
        result = homestead.public(state, now)
        result.update(message=message, effects=self.effects(state, now),
                      sell_stars=homestead.star_status(state, now, self.settings.sell_stars_daily, self.settings.sell_coins_per_star),
                      shards=conn.execute('SELECT shards FROM users WHERE id=?', (user['id'],)).fetchone()[0], **extra)
        return result

    def trade(self, conn, user, shop_id, action, body):
        shop, state, now = self.prepare(conn, user, shop_id, body)
        spec = shop[action].get(body.item)
        day = homestead.local_day(now)
        if not spec:
            fail('life_invalid_item')
        if not offered(shop, spec, day):
            fail('shop_item_unavailable')
        reserve(conn, user['id'], shop_id, action, body.item, spec, day, body.quantity)
        reference = str(body.request_id)
        amount = spec['coins'] * body.quantity
        stars = 0
        objects = []
        if action == 'buy':
            economy.change_coins(conn, user['id'], state, -amount, 'shop_buy', reference, now)
            if spec['shards']:
                self.money(conn, user['id'], -spec['shards'] * body.quantity, 'shop_buy', reference)
            if spec['kind'] == 'bag':
                homestead.add(state, body.item, body.quantity)
            elif spec['kind'] == 'decoration':
                for _ in range(body.quantity):
                    obj = npc_homes.return_gift(conn, self.assets, user['id'], 'regular', now,
                                                preset=DECORATIONS[body.item], key='shop_' + body.item)
                    conn.execute('UPDATE objects SET name=? WHERE id=?', (spec['name'], obj))
                    objects.append(obj)
            message = f'{spec["name"]} {body.quantity}개를 샀어요.'
        else:
            try:
                homestead.spend(state, body.item, body.quantity)
            except homestead.Rejected as error:
                fail(str(error))
            economy.change_coins(conn, user['id'], state, amount, 'shop_sell', reference, now)
            # All shops, services and legacy sales share the same saved carry and ledger cap.
            stars = homestead.sell_stars(state, amount, now, self.settings.sell_stars_daily, self.settings.sell_coins_per_star)
            if stars:
                self.money(conn, user['id'], stars, 'sell_reward', reference)
            message = f'{homestead.object_word(homestead.NAMES[body.item])} 팔고 잎전 {amount}개'
            message += f'와 별씨 {stars}개를 받았어요.' if stars else '를 받았어요.'
        return self.finish(conn, user, state, now, message, stars=stars, object_ids=objects)

    def service(self, conn, user, shop_id, body):
        shop, state, now = self.prepare(conn, user, shop_id, body)
        spec = shop['services'].get(body.service)
        if not spec:
            fail('shop_service_not_found', 404)
        if spec['kind'] == 'sell':
            return self.trade(conn, user, shop_id, 'sell', body)
        if body.quantity != 1 or body.item:
            fail('shop_invalid_service_arguments', 422)
        if spec['kind'] == 'order':
            return self.order(conn, user, body)
        reserve(conn, user['id'], shop_id, 'service', body.service, spec, homestead.local_day(now), 1)
        economy.change_coins(conn, user['id'], state, -spec['coins'], 'shop_service', str(body.request_id), now)
        state['shop_effects'] = self.effects(state, now)
        state['shop_effects']['cafe_mood'] = {'mood': spec['mood'], 'expires_at': now + spec['seconds']}
        return self.finish(conn, user, state, now, '따뜻한 차를 마시니 마음이 편안해졌어요.')

    def order(self, conn, user, body):
        state = life_state(conn, user['id'])
        now = self.clock()
        if body.version != state['version']:
            fail('stale_life_version')
        if state['order_day'] == homestead.local_day(now):
            fail('life_order_completed')
        spec = SHOPS['farm_stall']['services']['daily_order']
        try:
            for item, quantity in spec['items'].items():
                homestead.spend(state, item, quantity)
        except homestead.Rejected as error:
            fail(str(error))
        state['order_day'] = homestead.local_day(now)
        economy.change_coins(conn, user['id'], state, spec['coins_reward'], 'daily_order', str(body.request_id), now)
        return self.finish(conn, user, state, now, '마을 식탁 배달 완료! 잎전 20개를 받았어요.')
