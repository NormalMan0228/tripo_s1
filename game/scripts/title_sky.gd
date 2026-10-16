extends ColorRect
## A living sky behind the title (World Labs 360° panorama, assets/ui/title_sky.webp, from the 07
## session): the equirectangular picture seen through a perspective camera that turns slowly
## around (about 1.5° a second), so clouds drift past the logo without resampling a flat picture
## (the old slow zoom shimmered). The camera looks a little up so the sea sits low and the sky
## fills the logo's side. A canvas shader, one quad: no 3D scene, cheap on any machine.
const PANORAMA := "res://assets/ui/title_sky.webp"
const TURN := 1.5          # degrees a second
const PITCH := 22.0        # degrees up from the horizon: the sea is a band along the bottom
const FOV := 62.0          # vertical field of view, degrees

const SHADER := """
shader_type canvas_item;
uniform sampler2D pano : source_color, filter_linear_mipmap, repeat_enable;
uniform float yaw = 0.0;
uniform float pitch = 0.0;
uniform float fov = 1.08;
uniform float aspect = 1.6;
void fragment() {
	float h = tan(fov * 0.5);
	vec3 dir = normalize(vec3((UV.x - 0.5) * 2.0 * h * aspect, (0.5 - UV.y) * 2.0 * h, -1.0));
	float cp = cos(pitch), sp = sin(pitch);
	dir = vec3(dir.x, dir.y * cp - dir.z * sp, dir.y * sp + dir.z * cp);
	float cy = cos(yaw), sy = sin(yaw);
	dir = vec3(dir.x * cy - dir.z * sy, dir.y, dir.x * sy + dir.z * cy);
	float lon = atan(dir.x, -dir.z);
	float lat = asin(clamp(dir.y, -1.0, 1.0));
	vec2 uv = vec2(lon / 6.2831853 + 0.5, 0.5 - lat / 3.1415927);
	COLOR = vec4(textureLod(pano, uv, 0.0).rgb, 1.0);
}
"""

var turn := 0.0
var shader_material: ShaderMaterial

static func available() -> bool:
	return ResourceLoader.exists(PANORAMA)

func _ready() -> void:
	name = "TitleSky"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shader := Shader.new()
	shader.code = SHADER
	shader_material = ShaderMaterial.new()
	shader_material.shader = shader
	shader_material.set_shader_parameter("pano", load(PANORAMA))
	shader_material.set_shader_parameter("pitch", deg_to_rad(PITCH))
	shader_material.set_shader_parameter("fov", deg_to_rad(FOV))
	material = shader_material
	# A different start each time the title opens.
	turn = randf() * 360.0
	_apply()

func _process(delta: float) -> void:
	turn = fmod(turn + TURN * delta, 360.0)
	_apply()

func _apply() -> void:
	if shader_material == null: return
	shader_material.set_shader_parameter("yaw", deg_to_rad(turn))
	shader_material.set_shader_parameter("aspect", size.x / maxf(size.y, 1.0))
