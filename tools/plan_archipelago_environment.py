"""Plan the remaining reference props and a fifteen-model review checkpoint."""
import json
from pathlib import Path
from archipelago_queue import locked_queue

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/maps/archipelago_objects_v1'
STYLE = 'Single isolated game-ready 3D object for a colorful storybook archipelago with adult 1.70m cartoon people. High quality smooth 3D cartoon sculpt, rounded bevels, clean solid geometry, warm hand-painted PBR materials, visible subtle material grain, sophisticated stylized proportions, not a miniature toy. No ground plane, no background scenery, no people, no labels. '
SPECS = {
 '18_bridge_short': (3.2, 'An elegant gently arched cedar pedestrian bridge, 25m long and 4.8m wide, long direction X. Warm honey-orange timber plank walkway with a modest convex arch, sturdy vertical balusters, two continuous curved wooden top rails, carved round finials and amber post caps. Four symmetrically paired railing posts on each side. Both open ends allow adults to walk through. Rails 1.10m above the continuous solid deck. No steps, roof or decorative stairs. Thick board deck with no gaps or holes.'),
 '19_bridge_long': (3.6, 'A grand long oak pedestrian bridge to a lighthouse island, 30m long and 4.8m wide, long direction X. A sweeping but walkable timber arch with broad amber planks, two substantial curved handrails, heavier square posts topped with cream-white rounded caps, diagonal bracing below each rail and a visibly thick reinforced underdeck. Dark brown support beams underneath. Open level approaches at both ends, rails 1.10m above deck. No roof or staircase, no water or shores.'),
 '48_bridge_rope': (2.6, 'A rustic level-end wooden footbridge, 22m long by 4.2m wide, long direction X. Distinct straight golden plank deck with a very shallow central sag, a continuous solid walkway, sturdy dark timber posts, two thick natural tan rope handrails with loose irregular catenary curves and rope knots around each post. Solid knee-height crossed timber rail bracing beneath the rope. Handrail height 1.10m above planks. Safe stable walkway, open ends, no roof, no island, no stairs.'),
 '49_bridge_boardwalk': (2.2, 'A coastal flat timber boardwalk bridge, 19m long by 4.5m wide, long direction X. Distinct almost level pale weathered wood deck, sturdy teal-painted square posts, cream horizontal double-rail balustrades and dark oak underdeck beams. Flat pedestrian walkway, slightly flared welcoming ends, post caps rounded and simple. Rails 1.10m above the solid thick deck, no holes. Open walk-through at both ends, no stairs, no roof, no scenery.'),
 '20_pier': (1.65, 'A honey-brown wooden boat pier, 6m long and 3m wide. Closely fitted thick rounded plank platform with four stout cylindrical timber piles extending below the deck, a simple short wooden rail at the far end, two open approach ends. Warm wood grain, rope bindings on two piles. No water, shore, boats, lanterns or ramp.'),
 '21_boat': (.75, 'A small classic honey-brown wooden rowboat, 3.4m long by 1.3m wide, with a hollow open interior, curved clinker plank hull, cream rim, two wooden bench seats and two loose wooden oars inside. Rounded bow and stern. No people, water, mast or engine.'),
 '22_tent_orange': (2.05, 'A single orange and cream canvas A-frame camping tent, 2.05m tall, 2.7m deep and 2.1m wide. Warm orange side fabric, cream front flaps folded apart around a triangular open entrance, small dark interior and grounded wooden tent poles. Thick believable fabric with subtle folds, four small rope guy lines and pegs. No campsite or ground sheet extending around the model.'),
 '23_tent_green': (2.05, 'A single sage-green and pale cream A-frame camping tent, 2.05m tall, 2.6m deep and 2.1m wide. Green side canvas, cream front flaps open around a dark triangular entrance, small grounded timber support poles and four restrained rope guy lines. Softly rounded canvas folds, visible stitched seams. No surroundings.'),
 '24_firepit': (.58, 'A low circular campfire pit, 1.6m across, made from ten individually uneven rounded gray stones around five warm brown wooden logs arranged in a radial crisscross stack. Logs charred darker at tips. The entire object is low, grounded, coherent and solid. Empty space between the stones and logs, no flames, particles, glowing spheres, ground or scenery. This is the physical hearth asset for an animated fire.'),
 '25_picnic_table': (.82, 'A classic warm reddish honey timber picnic table, 2.1m long, with two attached long plank benches, thick rectangular tabletop with four boards, broad stable A-frame legs, rounded edges and visible restrained wood grain. Adult seat height 0.45m, table height 0.82m. No food or scenery.'),
 '26_bench': (.98, 'A cozy honey-brown wooden park bench, 1.9m wide and 0.98m tall. Rounded vertical short posts, three broad wooden slats for the comfortable backrest, two sturdy slats for the seat, four dark brown wooden legs, low curved armrests. Adult seat height 0.45m. Subtle wood grain, warm rounded sturdy construction. No floor or vegetation.'),
 '27_lamp': (3.15, 'A single black wrought-iron garden street lamp, 3.15m tall. Slim straight dark iron post with a slightly wider stable round base, elegant small ring mouldings and a classic four-sided tapering lantern at the top. Lantern has dark metal corner framing, warm pale yellow glass panes and a peaked black cap with a small finial. Glass panels solid, not missing. One lantern, no cables, foliage, ground, glow halo or background.'),
 '28_beach_umbrella': (2.35, 'A single blue and white striped round beach parasol, 2.35m tall and 2.6m canopy diameter. Eight alternating blue and cream white canvas wedges, gently domed scalloped rim, pale wooden pole grounded at center and small blue finial. Subtle cloth seams. No sand, chairs, table or landscape.'),
 '29_beach_lounger': (.85, 'A single cozy brown timber beach lounge chair for an adult, 1.9m long, with a reclined adjustable slatted back, long slatted seat, curved rounded wooden arm supports and four low sturdy legs. Warm honey wood grain, clean solid geometry. No pillow, parasol, sand or scenery.'),
 '30_cafe_umbrella': (2.45, 'A single cream white round cafe parasol, 2.45m tall, 2.5m canopy diameter, gently scalloped cloth canopy with radial seams. Honey timber center pole and small round weighted dark wood base. Restrained cloth folds, warm elegant cafe patio furniture. No table, chairs or scenery.'),
 '31_cafe_table': (.78, 'A small round wooden cafe table for two adults, 0.78m tall and 0.90m diameter. Warm honey wood circular top with four fitted plank segments, rounded rim, a thick central pedestal and four short stable radial feet. No chairs, cups, scenery or food.'),
 '32_cafe_chair': (.93, 'A single warm honey timber cafe chair, 0.93m tall, adult seat height 0.45m. Rounded square seat, gently curved slatted backrest, four sturdy tapered wood legs and short cross supports. Comfortable believable adult proportions. No armrests, table, ground or decor.'),
 '33_signboard': (1.08, 'A single small rustic A-frame chalkboard sandwich sign, 1.08m tall by 0.62m wide. Thick warm honey wood frame around a matte dark charcoal black blank board, second blank board behind connected by a hinge, visible sturdy A-shaped side supports. No written words, icons, text, ground or scenery.'),
 '34_timber_fence': (1.02, 'A single 2.2m-wide low rustic garden fence section, 1.02m tall. Two thick warm honey-brown squared posts with rounded caps, two horizontal wooden rails spanning the posts, short dark stake bases. Soft edge bevels and gentle wood grain, no scenery, gate, plants or floor.'),
 '35_picket_fence': (.90, 'A single 2m-wide cream-white painted garden picket fence section, 0.90m tall. Seven thick vertical wooden pickets with rounded pointed top ends, two white horizontal support rails behind, two stout white end posts with rounded pyramid caps. Clean solid timbers, subtle weathering. No gate, ground or plants.'),
 '36_speaker': (1.25, 'A single charcoal black outdoor music stage speaker cabinet, 1.25m tall, 0.52m wide. A rounded rectangular cabinet on a small stable foot, a large circular dark woofer with visible mesh grille and a smaller round tweeter above, simple side grip recess. Restrained modern proportions to blend into a warm cartoon village. No logos, wires, lights, stage or scenery.'),
 '37_round_tree': (6.4, 'One lush round-canopy broadleaf tree, 6.4m tall. A thick warm brown trunk splits into three short curved branches, supporting an asymmetric clustered crown of rounded dense leaf masses in lime, yellow-green and medium fresh green. Many distinct softly sculpted leafy clumps, large clean silhouette, subtle fine leaf texture. Crown fuller on one side, trunk visible beneath. Solid volumetric foliage, no flat leaf cards, flowers, fruit, roots spreading wide, rocks or ground.'),
 '38_conifer': (6.8, 'One tall stylized conifer pine tree, 6.8m tall. A short visible warm brown trunk, four overlapping organic rounded tiered conical needle bough layers, rich dark teal green foliage with lighter tips. Slightly asymmetric scalloped tier edges and convincing dense full canopy volume, rounded crown point. No flat billboards, separate leaves floating, snow, ground or scenery.'),
 '39_palm': (5.2, 'One small graceful tropical palm tree, 5.2m tall. A slim gently curved golden-brown ringed trunk and an irregular radial crown of seven broad arching green palm fronds. Each frond thick sculpted and volumetric with clean leaf lobes, fronds naturally vary in length and curvature. Warm coastal storybook palette. No coconuts, pot, terrain or scenery.'),
 '40_shrub': (1.05, 'One low compact leafy garden shrub, 1.05m tall and 1.35m wide. An irregular cluster of six softly rounded dense leaf clumps, mixed warm yellow green and darker emerald green, fine sculpted leaf detail and natural asymmetry. Solid volumetric foliage, small grounded brown stem base. No flowers, pot, pebbles, ground disk or flat leaf cards.'),
 '41_planter': (.72, 'A single terracotta flower pot, 0.72m tall overall. A thick tapered warm orange clay pot with a broad rounded lip and dark soil inside, holding one small bush of green leaves with a few delicate white and yellow daisy blooms. Visible matte clay grain, rounded believable pot and solid sculpted foliage. No ground or surrounding plants.'),
 '42_white_flowers': (.52, 'A small natural clump of five white daisies, 0.52m tall and 0.50m wide. Thick green stems with clean small sculpted broad leaves, five differently tilted white petal flowers with warm yellow centers, blooms at varied heights. Soft rounded solid petals, delicate but game-ready substantial geometry. Grounded grouped stems, no pot, soil disk or terrain.'),
 '43_yellow_flowers': (.45, 'A small natural clump of six golden yellow buttercup flowers, 0.45m tall and 0.55m wide. Several differently curved green stems, small rich green leaves and softly rounded yellow cupped petals with deeper orange centers. Blooms at staggered heights. Game-ready sculpted solid flowers, no pot, ground disk or scenery.'),
 '44_pink_flowers': (.48, 'A small natural garden clump of five pale pink flowers, 0.48m tall. Rich green stems and small rounded leaves, broad softly sculpted pink petals with warm yellow centers, varied bloom orientation and height. Cozy storybook garden palette, clean solid flower geometry. No pot, terrain disk or scene.'),
 '45_reeds': (1.25, 'A single natural pond-edge reed clump, 1.25m tall and 0.6m wide. Eight slightly curved thick tapered green rush leaves emerging from a tight grounded cluster, three slender warm brown cattail stalks with dark cylindrical seed heads. Leaves in varied heights and directions, substantial sculpted geometry. No pond, water, soil disk or ground.'),
 '46_water_lily': (.20, 'One small floating water lily cluster, 0.85m wide. Four flat but thick rounded bright green lily pads with small wedge cutouts at their rims, subtly curved glossy top surfaces, one delicate warm yellow flower on a short green stem rising 0.20m above the pads. Pads form one irregular natural cluster. No water plane, soil, pot or background.'),
 '47_starfish': (.08, 'A single small coral-red five-arm sea star, 0.26m tip-to-tip and 0.08m thick. Softly rounded fleshy tapered arms in a slightly irregular natural pose, subtle orange highlights and tiny rounded surface bumps. Warm stylized beach prop, solid volume, no sand, water, terrain disk or scenery.'),
}
BRIDGE_HEIGHTS = {'18_bridge_short':1.9, '19_bridge_long':2.1, '48_bridge_rope':1.85, '49_bridge_boardwalk':1.6}
for ident, calibrated_height in BRIDGE_HEIGHTS.items():
    SPECS[ident] = (calibrated_height, SPECS[ident][1])
BATCH = ['18_bridge_short','19_bridge_long','48_bridge_rope','49_bridge_boardwalk','37_round_tree','38_conifer','39_palm','40_shrub','42_white_flowers','43_yellow_flowers','27_lamp','26_bench','22_tent_orange','23_tent_green','24_firepit']

with locked_queue() as queue:
    active = queue['active_batch']
    if active['id'] != 'batch_02_links_nature_camp':
        assert active['status'] == 'approved_and_placed'
        queue.setdefault('batch_history', []).append(dict(active))
        for ident, name, location in [('48_bridge_rope','밧줄 난간 수로 다리','남서 섬과 남동 섬 사이'),('49_bridge_boardwalk','청록 난간 데크형 다리','북동 섬과 남동 섬 사이')]:
            if not any(i['id']==ident for i in queue['items']):
                queue['items'].append({'id':ident,'name':name,'reference_location':location,'category':'bridge','target_height_m':None,'review_status':'planned'})
        queue['active_batch'] = {'id':'batch_02_links_nature_camp','assets':BATCH,'max_concurrent':3,'max_observed_concurrent':0,'status':'authorized',
            'approval_evidence':'User: 그리고 각 지형을 이어주는 다리를 만들어주세요. 다리는 각각 모습이 달라야 합니다. 자연물이나 가로등, 그리고 그 외 레퍼런스 이미지에 있는 오브젝트를 생성해서 이 모든 것들을 배치해주세요.',
            'checkpoint_policy':'User confirmation after each 15 generated models; placement previews authorized in this request.'}
    for item in queue['items']:
        ident = item['id']
        if ident not in SPECS:
            continue
        height, description = SPECS[ident]
        prompt = STYLE + description
        assert len(prompt) <= 1024, (ident,len(prompt))
        item['target_height_m'] = height
        item['review_azimuth'] = .62 if item['category']=='bridge' else -.12
        item['generation_method'] = 'text'
        item['face_limit'] = 30000 if item['category']=='bridge' else 20000
        folder = BASE/ident
        folder.mkdir(exist_ok=True)
        (folder/'tripo_prompt.txt').write_text(prompt,encoding='utf-8')
        item['design_prompt'] = str((folder/'tripo_prompt.txt').relative_to(ROOT)).replace('\\','/')
        if item['category']=='bridge':
            item['target_dimensions_m'] = {'18_bridge_short':[4.8,25,1.9], '19_bridge_long':[4.8,30,2.1], '48_bridge_rope':[4.2,22,1.85], '49_bridge_boardwalk':[4.5,19,1.6]}[ident]
    assert len(queue['active_batch']['assets']) == 15
print('ENVIRONMENT_BATCH_AUTHORIZED models=15 bridges=4 max_concurrent=3')
