extends RefCounted
## The game's painted logo (assets/ui/logo.png, keyed from a generated sheet by
## tools/build_brand_art.py), shared by the title screen and the first loading card.
const LOGO := "res://assets/ui/logo.png"

## The logo at `width` logical pixels, its height following the picture.
static func logo(width: float) -> TextureRect:
	var rect := TextureRect.new()
	var texture: Texture2D = load(LOGO)
	rect.texture = texture
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	# Shown well below its pixel size: mipmaps keep the outline smooth.
	rect.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	rect.custom_minimum_size = Vector2(width, width*texture.get_height()/texture.get_width())
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect
