"""The archetype library: object types the game knows how to bring to life, as plain data.

server/archetypes.py reads it; adding a type is adding one entry here (bump VERSION when an
existing entry changes, so learned designs made with the old wording are not reused).

Each archetype:
  id         the type, also what the LLM designer puts in plan.category
  names      ko/en display names
  words      what players call it (Korean words match the end of a word, after a particle is
             dropped: '흔들의자를' -> '흔들의자'; English words match whole words, plural too)
  roles      the parts the type is made of, by the id the designer gives them:
               id     the part id the designer is asked to use (and the fixture uses)
               words  other part ids that mean the same role ('hourHand', 'clock_case')
               root   a missing root role takes the first part without a parent
               primitive  a part the game makes itself (no Tripo credits): 'make' names the shape
                      (server/clock_hands.py: hour, minute, second, pendulum)
               hint   what the designer is told the part is
  behaviours interaction presets (server/interactions.py Preset) with 'role' instead of
             'target'; or_whole: when that part is missing, the whole object does it
  single     presets for a one-piece craft (static crafts, or the credit-cap fallback)
  rest       '' | 'sit' | 'lie' (rooms seat or lay the walker on it)
  override   the type's behaviours win over a crafted program (a clock must show real time);
             otherwise a craft that already moves keeps its own motion
  always_moving  built with its moving parts even when the player asked for a still piece (a clock
             always gets its hands; they cost nothing), when the craft fits the credit cap
  accent     the role that glows in styles whose palette glows (sci-fi clocks)
  hint       one more sentence for the designer
  fixture    the offline designer's plan (development and tests): title + parts
"""

VERSION = 1

# Angles: hinge/rock degrees; tick degrees per step; slide centimetres. axis: the part's local axis.
ARCHETYPES = [
    {'id': 'clock', 'names': {'ko': '시계', 'en': 'Clock'},
     'words': ['시계', '벽시계', '탁상시계', '괘종시계', '뻐꾸기시계', 'clock', 'wall clock', 'grandfather clock', 'cuckoo clock'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'dial', 'face', 'frame', 'housing', 'cabinet'], 'root': True,
          'hint': 'the clock case with a BLANK dial: no hands drawn or modelled on it'},
         {'id': 'hour_hand', 'words': ['hour'], 'primitive': True, 'make': 'hour',
          'hint': 'short thin flat bar, size about [.05,.24,.025], parent body, pivot [0,-.4,0], position at the dial centre just in front of the dial (+Z)'},
         {'id': 'minute_hand', 'words': ['minute'], 'primitive': True, 'make': 'minute',
          'hint': 'longer thin flat bar, size about [.035,.36,.02], parent body, pivot [0,-.4,0], same position as the hour hand but slightly further in front'},
         {'id': 'second_hand', 'words': ['second'], 'primitive': True, 'make': 'second', 'optional': True,
          'hint': 'optional very thin red bar, size about [.02,.4,.02], parent body, pivot [0,-.3,0], in front of the minute hand'},
         {'id': 'pendulum', 'words': ['pendulum', 'bob'], 'primitive': True, 'make': 'pendulum', 'optional': True,
          'hint': 'optional pendulum (tall clocks only): thin bar, parent body, pivot [0,.5,0] at its top, below the dial'},
     ],
     'behaviours': [
         {'role': 'hour_hand', 'kind': 'clock', 'hand': 'hour', 'axis': 'z'},
         {'role': 'minute_hand', 'kind': 'clock', 'hand': 'minute', 'axis': 'z'},
         {'role': 'second_hand', 'kind': 'clock', 'hand': 'second', 'axis': 'z'},
         {'role': 'pendulum', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1},
     ],
     'single': [], 'rest': '', 'override': True, 'always_moving': True, 'accent': 'second_hand',
     'hint': 'The game turns the hands to the player\'s local time, so the program may stay empty.',
     'fixture': {'title': '벽시계', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.9, .9, .14], 'position': [0, .62, 0], 'color': '#efe6d2'},
         {'id': 'hour_hand', 'parent': 'body', 'shape': 'box', 'size': [.05, .24, .025], 'position': [0, 0, .085], 'pivot': [0, -.4, 0], 'color': '#2f2a24'},
         {'id': 'minute_hand', 'parent': 'body', 'shape': 'box', 'size': [.035, .36, .02], 'position': [0, 0, .1], 'pivot': [0, -.4, 0], 'color': '#2f2a24'},
         {'id': 'second_hand', 'parent': 'body', 'shape': 'box', 'size': [.02, .4, .02], 'position': [0, 0, .114], 'pivot': [0, -.3, 0], 'color': '#c0392b'}]}},

    {'id': 'door', 'names': {'ko': '문', 'en': 'Door'},
     'words': ['문', '대문', '출입문', '현관문', '쪽문', '여닫이문', '문짝', 'door', 'gate', 'doorway'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'wall', 'post', 'arch', 'jamb', 'body'], 'root': True, 'hint': 'the frame around the opening'},
         {'id': 'door', 'words': ['door', 'gate', 'leaf', 'panel'], 'hint': 'the door leaf, parent frame, pivot [-.5,0,0] at its hinge edge'},
     ],
     'behaviours': [{'role': 'door', 'kind': 'hinge', 'trigger': 'near', 'axis': 'y', 'angle': -100}],
     'single': [], 'rest': '',
     'fixture': {'title': '나무 문', 'parts': [
         {'id': 'frame', 'shape': 'box', 'size': [1.2, 2.2, .1], 'position': [0, 1.1, 0], 'color': '#8f6244'},
         {'id': 'door', 'parent': 'frame', 'shape': 'box', 'size': [.9, 2.0, .06], 'position': [-.45, -.05, .09], 'pivot': [-.5, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'chest', 'names': {'ko': '상자', 'en': 'Chest'},
     'words': ['상자', '보물상자', '궤짝', '함', '보석함', '트렁크', 'chest', 'box', 'crate', 'trunk', 'coffer'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'box', 'case'], 'root': True, 'hint': 'the box'},
         {'id': 'lid', 'words': ['lid', 'cover', 'top'], 'hint': 'the lid, pivot [0,0,-.5] at its back edge'},
     ],
     'behaviours': [{'role': 'lid', 'kind': 'hinge', 'trigger': 'click', 'axis': 'x', 'angle': -100}],
     'single': [], 'rest': ''},

    {'id': 'cabinet', 'names': {'ko': '수납장', 'en': 'Cabinet'},
     'words': ['찬장', '장롱', '옷장', '수납장', '캐비닛', '진열장', '사물함', '장식장', 'cabinet', 'wardrobe', 'cupboard', 'closet', 'locker'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'carcass', 'frame'], 'root': True, 'hint': 'the cabinet body'},
         {'id': 'door', 'words': ['door', 'leaf', 'panel'], 'hint': 'the front door, parent body, pivot [-.5,0,0] at its hinge edge'},
     ],
     'behaviours': [{'role': 'door', 'kind': 'hinge', 'trigger': 'click', 'axis': 'y', 'angle': -100}],
     'single': [], 'rest': '',
     'fixture': {'title': '수납장', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [1.0, 1.7, .5], 'position': [0, .85, 0], 'color': '#a87c56'},
         {'id': 'door', 'parent': 'body', 'shape': 'box', 'size': [.95, 1.6, .04], 'position': [-.475, 0, .27], 'pivot': [-.5, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'drawer', 'names': {'ko': '서랍장', 'en': 'Drawers'},
     'words': ['서랍', '서랍장', '협탁', '화장대', 'drawer', 'drawers', 'dresser', 'nightstand', 'chest of drawers'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'frame', 'cabinet'], 'root': True, 'hint': 'the case'},
         {'id': 'drawer', 'words': ['drawer'], 'hint': 'one drawer, parent body, closed position flush with the front (+Z)'},
     ],
     'behaviours': [{'role': 'drawer', 'kind': 'slide', 'trigger': 'click', 'axis': 'z', 'angle': 30}],
     'single': [], 'rest': '',
     'fixture': {'title': '서랍장', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.9, .8, .55], 'position': [0, .4, 0], 'color': '#a87c56'},
         {'id': 'drawer', 'parent': 'body', 'shape': 'box', 'size': [.8, .24, .5], 'position': [0, .17, .05], 'color': '#d6b48a'}]}},

    {'id': 'lamp', 'names': {'ko': '램프', 'en': 'Lamp'},
     'words': ['램프', '스탠드', '조명', '등', '전등', '가로등', '무드등', '샹들리에', 'lamp', 'light', 'chandelier', 'streetlight', 'lamppost'],
     'roles': [
         {'id': 'base', 'words': ['base', 'stand', 'pole', 'body', 'post'], 'root': True, 'hint': 'the stand'},
         {'id': 'shade', 'words': ['shade', 'bulb', 'light', 'lamp', 'glass', 'globe', 'head'], 'hint': 'the shade or bulb that lights up'},
     ],
     'behaviours': [{'role': 'shade', 'kind': 'glow', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'glow', 'trigger': 'click', 'level': 2}], 'rest': ''},

    {'id': 'lantern', 'names': {'ko': '랜턴', 'en': 'Lantern'},
     'words': ['랜턴', '등롱', '등불', '초롱', '호롱', '호롱불', '청사초롱', 'lantern'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'body', 'case', 'base'], 'root': True, 'hint': 'the lantern frame'},
         {'id': 'flame', 'words': ['flame', 'glass', 'light', 'candle', 'fire'], 'hint': 'the glowing glass or flame'},
     ],
     'behaviours': [{'role': 'flame', 'kind': 'flicker', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'flicker', 'trigger': 'click', 'level': 2}], 'rest': '',
     'fixture': {'title': '등불', 'parts': [
         {'id': 'whole', 'shape': 'ellipsoid', 'size': [.4, .6, .4], 'position': [0, .3, 0], 'color': '#d9a441'}]}},

    {'id': 'candle', 'names': {'ko': '양초', 'en': 'Candle'},
     'words': ['양초', '촛불', '촛대', '캔들', 'candle', 'candles', 'candlestick', 'candelabra'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'holder', 'stick', 'wax'], 'root': True, 'hint': 'the candle and holder'},
         {'id': 'flame', 'words': ['flame', 'fire', 'wick', 'light'], 'hint': 'the flame'},
     ],
     'behaviours': [{'role': 'flame', 'kind': 'flicker', 'trigger': 'always', 'level': 1, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'flicker', 'trigger': 'always', 'level': 1}], 'rest': '',
     'fixture': {'title': '양초', 'parts': [
         {'id': 'whole', 'shape': 'box', 'size': [.14, .4, .14], 'position': [0, .2, 0], 'color': '#f3e6c4'}]}},

    {'id': 'fan', 'names': {'ko': '선풍기', 'en': 'Fan'},
     'words': ['선풍기', '환풍기', '탁상선풍기', 'fan', 'desk fan', 'electric fan', 'ventilator'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'stand', 'pole', 'housing'], 'root': True, 'hint': 'stand and motor'},
         {'id': 'blades', 'words': ['blade', 'rotor', 'propeller', 'fan', 'wing'], 'hint': 'the blade rotor facing front (+Z), parent body'},
     ],
     'behaviours': [{'role': 'blades', 'kind': 'rotor', 'trigger': 'click', 'axis': 'z', 'level': 3}],
     'single': [], 'rest': '',
     'fixture': {'title': '선풍기', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.16, 1.0, .16], 'position': [0, .5, 0], 'color': '#dfe6e9'},
         {'id': 'blades', 'parent': 'body', 'shape': 'box', 'size': [.9, .1, .03], 'position': [0, .42, .12], 'color': '#74b9ff'}]}},

    {'id': 'ceiling_fan', 'names': {'ko': '실링팬', 'en': 'Ceiling fan'},
     'words': ['실링팬', '천장선풍기', 'ceiling fan'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'mount', 'motor'], 'root': True, 'hint': 'the mount and motor'},
         {'id': 'blades', 'words': ['blade', 'rotor', 'propeller', 'fan'], 'hint': 'the flat blade rotor, parent body'},
     ],
     'behaviours': [{'role': 'blades', 'kind': 'rotor', 'trigger': 'always', 'axis': 'y', 'level': 2}],
     'single': [], 'rest': ''},

    {'id': 'windmill', 'names': {'ko': '풍차', 'en': 'Windmill'},
     'words': ['풍차', '바람개비', 'windmill', 'pinwheel', 'wind turbine'],
     'roles': [
         {'id': 'tower', 'words': ['tower', 'body', 'base', 'stick', 'pole', 'house'], 'root': True, 'hint': 'the tower or stick'},
         {'id': 'sails', 'words': ['sail', 'blade', 'rotor', 'wheel', 'wing', 'vane'], 'hint': 'the sail rotor facing front (+Z), parent tower'},
     ],
     'behaviours': [{'role': 'sails', 'kind': 'rotor', 'trigger': 'always', 'axis': 'z', 'level': 1}],
     'single': [], 'rest': '',
     'fixture': {'title': '풍차', 'parts': [
         {'id': 'tower', 'shape': 'box', 'size': [.8, 1.6, .8], 'position': [0, .8, 0], 'color': '#c9a46e'},
         {'id': 'sails', 'parent': 'tower', 'shape': 'box', 'size': [1.6, .18, .04], 'position': [0, .55, .44], 'color': '#f5f0e6'}]}},

    {'id': 'waterwheel', 'names': {'ko': '물레방아', 'en': 'Water wheel'},
     'words': ['물레방아', '수차', '물레', 'waterwheel', 'water wheel', 'mill wheel', 'spinning wheel'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'body', 'base', 'stand', 'house'], 'root': True, 'hint': 'the frame'},
         {'id': 'wheel', 'words': ['wheel', 'rotor', 'paddle'], 'hint': 'the wheel turning about the x axis, parent frame'},
     ],
     'behaviours': [{'role': 'wheel', 'kind': 'rotor', 'trigger': 'always', 'axis': 'x', 'level': 1}],
     'single': [], 'rest': '',
     'fixture': {'title': '물레방아', 'parts': [
         {'id': 'frame', 'shape': 'box', 'size': [.2, .9, 1.2], 'position': [-.3, .45, 0], 'color': '#8f6244'},
         {'id': 'wheel', 'parent': 'frame', 'shape': 'box', 'size': [.12, 1.1, .16], 'position': [.25, .1, 0], 'color': '#c79a6b'}]}},

    {'id': 'plant', 'names': {'ko': '화분', 'en': 'Plant'},
     'words': ['화분', '식물', '화초', '꽃', '선인장', '분재', '관엽식물', '야자수', 'plant', 'potted plant', 'tree', 'flower', 'flowers', 'bush', 'cactus', 'bonsai', 'palm'],
     'roles': [
         {'id': 'pot', 'words': ['pot', 'base', 'planter', 'vase'], 'root': True, 'hint': 'the pot'},
         {'id': 'leaves', 'words': ['leaf', 'leaves', 'plant', 'foliage', 'crown', 'flower', 'tree'], 'hint': 'the plant, parent pot, pivot [0,-.5,0] at its base'},
     ],
     'behaviours': [{'role': 'leaves', 'kind': 'sway', 'trigger': 'near', 'level': 1, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'sway', 'trigger': 'near', 'level': 1}], 'rest': ''},

    {'id': 'flag', 'names': {'ko': '깃발', 'en': 'Flag'},
     'words': ['깃발', '깃대', '현수막', '배너', '휘장', 'flag', 'banner', 'pennant'],
     'roles': [
         {'id': 'pole', 'words': ['pole', 'mast', 'stand', 'base', 'post'], 'root': True, 'hint': 'the pole'},
         {'id': 'cloth', 'words': ['cloth', 'flag', 'banner', 'fabric', 'sheet'], 'hint': 'the cloth, parent pole, pivot [-.5,0,0] at the pole'},
     ],
     'behaviours': [{'role': 'cloth', 'kind': 'rock', 'trigger': 'always', 'axis': 'y', 'level': 2}],
     'single': [{'role': 'whole', 'kind': 'sway', 'trigger': 'always', 'level': 1}], 'rest': '',
     'fixture': {'title': '깃발', 'parts': [
         {'id': 'pole', 'shape': 'box', 'size': [.06, 2.0, .06], 'position': [0, 1.0, 0], 'color': '#8a6a4a'},
         {'id': 'cloth', 'parent': 'pole', 'shape': 'box', 'size': [.75, .48, .03], 'position': [.03, .68, 0], 'pivot': [-.5, 0, 0], 'color': '#c0392b'}]}},

    {'id': 'wind_chime', 'names': {'ko': '풍경', 'en': 'Wind chime'},
     'words': ['풍경', '윈드차임', '모빌', 'wind chime', 'windchime', 'mobile'],
     'roles': [
         {'id': 'top', 'words': ['top', 'hanger', 'roof', 'base', 'frame'], 'root': True, 'hint': 'the top it hangs from'},
         {'id': 'chimes', 'words': ['chime', 'bell', 'tube', 'hanging', 'pendant'], 'hint': 'the hanging part, parent top, pivot [0,.5,0] at its top'},
     ],
     'behaviours': [{'role': 'chimes', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1, 'or_whole': True},
                    {'role': 'chimes', 'kind': 'sway', 'trigger': 'near', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1}], 'rest': ''},

    {'id': 'rocking_chair', 'names': {'ko': '흔들의자', 'en': 'Rocking chair'},
     'words': ['흔들의자', '흔들 의자', 'rocking chair', 'rocker'],
     'roles': [{'id': 'whole', 'words': ['seat', 'chair', 'body'], 'root': True, 'hint': 'the chair'}],
     'behaviours': [{'role': 'whole', 'kind': 'rock', 'trigger': 'click', 'axis': 'x', 'level': 2}],
     'single': [{'role': 'whole', 'kind': 'rock', 'trigger': 'click', 'axis': 'x', 'level': 2}], 'rest': 'sit',
     'fixture': {'title': '흔들의자', 'parts': [
         {'id': 'rockers', 'shape': 'box', 'size': [.6, .06, .8], 'position': [0, .03, 0], 'color': '#8f6244'},
         {'id': 'legs', 'parent': 'rockers', 'shape': 'box', 'size': [.46, .36, .46], 'position': [0, .21, 0], 'color': '#a87c56'},
         {'id': 'seat', 'parent': 'legs', 'shape': 'box', 'size': [.58, .07, .56], 'position': [0, .215, 0], 'color': '#c79a6b'},
         {'id': 'back', 'parent': 'seat', 'shape': 'box', 'size': [.58, .62, .06], 'position': [0, .34, -.25], 'rotation': [-8, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'music_box', 'names': {'ko': '오르골', 'en': 'Music box'},
     'words': ['오르골', '뮤직박스', '음악상자', 'music box', 'musicbox'],
     'roles': [
         {'id': 'box', 'words': ['box', 'body', 'base', 'case'], 'root': True, 'hint': 'the box'},
         {'id': 'lid', 'words': ['lid', 'cover', 'top'], 'optional': True, 'hint': 'the lid, parent box, pivot [0,0,-.5] at its back edge'},
         {'id': 'dancer', 'words': ['dancer', 'figure', 'doll', 'ballerina', 'carousel', 'turntable', 'figurine'], 'hint': 'the little figure that turns, parent box'},
     ],
     'behaviours': [{'role': 'lid', 'kind': 'hinge', 'trigger': 'click', 'axis': 'x', 'angle': -100},
                    {'role': 'dancer', 'kind': 'turn', 'trigger': 'click', 'level': 2, 'or_whole': True},
                    {'role': 'whole', 'kind': 'pulse', 'trigger': 'click', 'level': 1}],
     'single': [{'role': 'whole', 'kind': 'turn', 'trigger': 'click', 'level': 1},
                {'role': 'whole', 'kind': 'pulse', 'trigger': 'click', 'level': 1}], 'rest': '',
     'fixture': {'title': '오르골', 'parts': [
         {'id': 'box', 'shape': 'box', 'size': [.6, .32, .42], 'position': [0, .16, 0], 'color': '#8f6244'},
         {'id': 'lid', 'parent': 'box', 'shape': 'box', 'size': [.6, .05, .42], 'position': [0, .185, -.21], 'pivot': [0, 0, -.5], 'color': '#a87c56'},
         {'id': 'dancer', 'parent': 'box', 'shape': 'ellipsoid', 'size': [.1, .24, .1], 'position': [0, .3, .05], 'color': '#f8c8dc'}]}},

    {'id': 'globe', 'names': {'ko': '지구본', 'en': 'Globe'},
     'words': ['지구본', '지구의', 'globe'],
     'roles': [
         {'id': 'stand', 'words': ['stand', 'base', 'frame'], 'root': True, 'hint': 'the stand'},
         {'id': 'sphere', 'words': ['sphere', 'globe', 'ball', 'earth', 'world'], 'hint': 'the globe, parent stand'},
     ],
     'behaviours': [{'role': 'sphere', 'kind': 'turn', 'trigger': 'click', 'level': 2}],
     'single': [], 'rest': ''},

    {'id': 'screen', 'names': {'ko': '텔레비전', 'en': 'Screen'},
     'words': ['텔레비전', '티비', '모니터', '스크린', '컴퓨터', 'tv', 'television', 'monitor', 'screen', 'computer'],
     'roles': [
         {'id': 'body', 'words': ['body', 'frame', 'case', 'stand', 'base'], 'root': True, 'hint': 'the set'},
         {'id': 'screen', 'words': ['screen', 'display', 'panel', 'monitor'], 'hint': 'the flat screen on the front (+Z), parent body'},
     ],
     'behaviours': [{'role': 'screen', 'kind': 'glow', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'glow', 'trigger': 'click', 'level': 1}], 'rest': '',
     'fixture': {'title': '텔레비전', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [1.1, .7, .12], 'position': [0, .6, 0], 'color': '#2d3436'},
         {'id': 'screen', 'parent': 'body', 'shape': 'box', 'size': [.95, .55, .02], 'position': [0, 0, .07], 'color': '#4a6c8c'}]}},

    {'id': 'sign', 'names': {'ko': '간판', 'en': 'Sign'},
     'words': ['간판', '표지판', '네온사인', '이정표', 'sign', 'signboard', 'signpost', 'neon sign'],
     'roles': [{'id': 'whole', 'words': ['board', 'sign', 'body'], 'root': True, 'hint': 'the sign'}],
     'behaviours': [{'role': 'whole', 'kind': 'pulse', 'trigger': 'always', 'level': 1}],
     'single': [{'role': 'whole', 'kind': 'pulse', 'trigger': 'always', 'level': 1}], 'rest': ''},

    {'id': 'bed', 'names': {'ko': '침대', 'en': 'Bed'},
     'words': ['침대', '이층침대', '싱글침대', '더블침대', '해먹', 'bed', 'bunk bed', 'hammock', 'futon'],
     'roles': [{'id': 'whole', 'words': ['frame', 'bed', 'body'], 'root': True, 'hint': 'the bed'}],
     'behaviours': [], 'single': [], 'rest': 'lie'},

    {'id': 'seat', 'names': {'ko': '의자', 'en': 'Seat'},
     'words': ['의자', '벤치', '소파', '쇼파', '스툴', '걸상', '안락의자', '왕좌', '좌식의자', 'chair', 'bench', 'sofa', 'couch',
               'stool', 'armchair', 'seat', 'throne', 'loveseat'],
     'roles': [{'id': 'whole', 'words': ['seat', 'chair', 'body', 'frame'], 'root': True, 'hint': 'the seat'}],
     'behaviours': [], 'single': [], 'rest': 'sit'},
]
