"""Task 73: Tripo rebuilds only what the concept picture shows, so an object touching or crossing the picture
edge comes back cut. cut_edges finds those sides (soft studio backgrounds stay quiet) and the job status
shows them so the window can warn and suggest a redraw."""
import io
from PIL import Image, ImageDraw, ImageFilter
from server.asset_studio import cut_edges, fixture_concept
from server.provider import jpeg_preview
from server.tests.test_concept import Provider, world, craft, run
from server.tests.test_studio import account


def background(centre=232, corner=None, tilt=0, size=(1024, 1024)):
    """Light-grey studio backdrop: flat, or with a radial vignette (corner value) and a top-to-bottom tilt."""
    w, h = size
    if corner is None and not tilt: return Image.new('RGB', size, (centre, centre, centre + 2))
    small = Image.new('RGB', (w // 4, h // 4)); px = small.load()
    for y in range(h // 4):
        for x in range(w // 4):
            r2 = (((x - w / 8) / (w / 8)) ** 2 + ((y - h / 8) / (h / 8)) ** 2) / 2
            v = centre + ((corner if corner is not None else centre) - centre) * r2 + tilt * (y / (h / 4) - 0.5)
            px[x, y] = (int(v), int(v), int(v) + 2)
    return small.resize(size, Image.BILINEAR)


def scene(back, box, colour=(140, 80, 40), ellipse=False, shadow=True):
    """An object (box) on the backdrop, with a soft contact shadow under it."""
    image = back.copy()
    if shadow:
        mask = Image.new('L', image.size, 0); ImageDraw.Draw(mask).ellipse((box[0], box[3] - 40, box[2], box[3] + 60), fill=90)
        image = Image.composite(Image.new('RGB', image.size, (120, 120, 125)), image, mask.filter(ImageFilter.GaussianBlur(40)))
    draw = ImageDraw.Draw(image)
    if ellipse: draw.ellipse(box, fill=colour, outline=(60, 40, 20), width=8)
    else: draw.rounded_rectangle(box, 30, fill=colour, outline=(60, 40, 20), width=8)
    return image


def jpeg(image):
    out = io.BytesIO(); image.save(out, 'JPEG', quality=85); return out.getvalue()


def test_a_centred_object_on_light_grey_is_whole():
    assert cut_edges(jpeg(scene(background(), (300, 260, 724, 700)))) == []
    assert cut_edges(jpeg(scene(background(), (300, 260, 724, 700), colour=(250, 250, 250)))) == []
    assert cut_edges(fixture_concept('a cosy chest')) == []


def test_an_object_touching_the_right_edge():
    assert cut_edges(jpeg(scene(background(), (600, 300, 1024, 700)))) == ['right']
    # Almost touching (inside the outer 1.5%) counts too: the margin is gone.
    assert cut_edges(jpeg(scene(background(), (600, 300, 1016, 700), shadow=False))) == ['right']


def test_an_object_crossing_the_top_and_left():
    assert sorted(cut_edges(jpeg(scene(background(), (-80, -80, 500, 500), ellipse=True)))) == ['left', 'top']
    # A grey object close to the backdrop's grey still shows.
    assert cut_edges(jpeg(scene(background(), (300, -30, 724, 500), colour=(170, 170, 175)))) == ['top']


def test_soft_gradients_and_vignettes_stay_background():
    for back in (background(centre=238, corner=170), background(centre=240, corner=140), background(centre=220, tilt=60)):
        assert cut_edges(jpeg(scene(back, (300, 260, 724, 700)))) == []
    # ...while an object at the edge of a vignetted picture is still found.
    assert cut_edges(jpeg(scene(background(centre=238, corner=170), (-20, 300, 400, 700)))) == ['left']


def test_a_thin_tip_or_a_wide_base():
    # A tip under 3% of the side is not worth a redraw; a base wider than the picture is cut on three sides.
    assert cut_edges(jpeg(scene(background(), (500, 500, 520, 1024), shadow=False))) == []
    assert sorted(cut_edges(jpeg(scene(background(), (-40, 600, 1064, 1100), shadow=False)))) == ['bottom', 'left', 'right']


def test_unreadable_pictures_give_no_sides():
    assert cut_edges(b'not a picture') == [] and cut_edges(b'') == []
    raw = io.BytesIO(); Image.new('RGB', (8, 8), 'white').save(raw, 'PNG')
    assert cut_edges(raw.getvalue()) == []


class CutProvider(Provider):
    """Tripo draws the object sitting on the bottom edge of the picture."""
    async def fetch_image(self, url):
        raw = io.BytesIO(); scene(background(), (300, 500, 724, 1030)).save(raw, 'PNG')
        return jpeg_preview(raw.getvalue())


def test_the_job_status_names_the_cut_sides(tmp_path):
    provider = CutProvider(); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=craft()).json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'awaiting_confirmation'
        assert value['concept']['edges'] == ['bottom']
        assert value['provenance']['concept']['edges'] == ['bottom']
        # Pricing and states are unchanged by the warning.
        assert value['concept']['estimate_with_concept'] == 35 and value['concept']['estimate_text_only'] == 25
