"""Conservative, token-based GDScript declarations and script-call checks.

This is deliberately not a Godot parser. Calls through instances, inner-class
names, native APIs, dynamically loaded scripts and ambiguous class names are
outside the method-existence check. No engine process or imports are required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import posixpath

from .common import Context, Source, Token, arguments, significant


# Common Godot 4 native bases, including editor/plugin and abstract classes.
# This offline list is intentionally explicit: a misspelled custom class must
# not be accepted simply because its name starts with an uppercase letter.
NATIVE_CLASSES = frozenset("""
Object RefCounted Resource Script GDScript CSharpScript Node Node2D Node3D
CanvasItem Control Container BoxContainer HBoxContainer VBoxContainer
GridContainer FlowContainer HFlowContainer VFlowContainer MarginContainer
PanelContainer ScrollContainer SplitContainer HSplitContainer VSplitContainer
AspectRatioContainer CenterContainer SubViewportContainer TabContainer
BaseButton Button CheckBox CheckButton LinkButton MenuButton OptionButton
TextureButton ColorPickerButton Label RichTextLabel LineEdit TextEdit CodeEdit
Panel Popup PopupPanel PopupMenu Window AcceptDialog ConfirmationDialog
FileDialog ColorPicker ColorRect TextureRect NinePatchRect GraphEdit GraphNode
GraphElement GraphFrame ItemList Tree TreeItem Range Slider HSlider VSlider
ScrollBar HScrollBar VScrollBar ProgressBar TextureProgressBar SpinBox
Separator HSeparator VSeparator TabBar VideoStreamPlayer ReferenceRect
TouchScreenButton MenuBar CanvasLayer CanvasModulate Timer SceneTree MainLoop
SceneTreeTimer Tween Tweener CallbackTweener IntervalTweener MethodTweener
PropertyTweener SubtweenTweener MultiplayerAPI SceneMultiplayer
MultiplayerPeer OfflineMultiplayerPeer ENetMultiplayerPeer WebRTCMultiplayerPeer
WebSocketMultiplayerPeer MultiplayerSpawner MultiplayerSynchronizer
Viewport SubViewport World2D World3D WorldEnvironment Environment
Camera2D Camera3D XRCamera3D XROrigin3D XRController3D XRNode3D XRAnchor3D
XRInterface XRInterfaceExtension XRTracker XRPositionalTracker XRHandTracker
VisualInstance3D GeometryInstance3D MeshInstance2D MeshInstance3D MultiMesh
MultiMeshInstance2D MultiMeshInstance3D SpriteBase3D Sprite3D AnimatedSprite3D
Sprite2D AnimatedSprite2D SpriteFrames Label3D Decal FogVolume VisualShader
Light2D PointLight2D DirectionalLight2D Light3D OmniLight3D DirectionalLight3D
SpotLight3D LightOccluder2D OccluderPolygon2D OccluderInstance3D Occluder3D
ArrayOccluder3D BoxOccluder3D SphereOccluder3D QuadOccluder3D PolygonOccluder3D
ReflectionProbe LightmapGI LightmapGIData VoxelGI VoxelGIData GPUParticles2D
GPUParticles3D CPUParticles2D CPUParticles3D GPUParticlesAttractor3D
GPUParticlesAttractorBox3D GPUParticlesAttractorSphere3D
GPUParticlesAttractorVectorField3D GPUParticlesCollision3D
GPUParticlesCollisionBox3D GPUParticlesCollisionHeightField3D
GPUParticlesCollisionSDF3D GPUParticlesCollisionSphere3D
CollisionObject2D CollisionObject3D Area2D Area3D PhysicsBody2D PhysicsBody3D
StaticBody2D StaticBody3D AnimatableBody2D AnimatableBody3D RigidBody2D
RigidBody3D CharacterBody2D CharacterBody3D VehicleBody3D VehicleWheel3D
SoftBody3D CollisionShape2D CollisionShape3D CollisionPolygon2D CollisionPolygon3D
RayCast2D RayCast3D ShapeCast2D ShapeCast3D SpringArm3D RemoteTransform2D
RemoteTransform3D Joint2D Joint3D PinJoint2D PinJoint3D GrooveJoint2D
DampedSpringJoint2D HingeJoint3D SliderJoint3D ConeTwistJoint3D Generic6DOFJoint3D
NavigationAgent2D NavigationAgent3D NavigationObstacle2D NavigationObstacle3D
NavigationRegion2D NavigationRegion3D NavigationLink2D NavigationLink3D
NavigationMesh NavigationPolygon NavigationPathQueryParameters2D
NavigationPathQueryParameters3D NavigationPathQueryResult2D NavigationPathQueryResult3D
Path2D Path3D PathFollow2D PathFollow3D Curve Curve2D Curve3D
Skeleton2D Bone2D Skeleton3D SkeletonIK3D SkeletonModifier3D BoneAttachment3D
PhysicalBone2D PhysicalBone3D PhysicalBoneSimulator3D Skin SkeletonProfile
SkeletonProfileHumanoid BoneMap RetargetModifier3D LookAtModifier3D
SpringBoneSimulator3D Animation AnimationLibrary AnimationMixer AnimationPlayer
AnimationTree AnimationNode AnimationRootNode AnimationNodeAnimation
AnimationNodeBlendTree AnimationNodeBlendSpace1D AnimationNodeBlendSpace2D
AnimationNodeStateMachine AnimationNodeStateMachinePlayback
AnimationNodeStateMachineTransition AnimationNodeExtension
AudioStream AudioStreamWAV AudioStreamOggVorbis AudioStreamMP3 AudioStreamPlayer
AudioStreamPlayer2D AudioStreamPlayer3D AudioStreamRandomizer AudioStreamGenerator
AudioStreamGeneratorPlayback AudioStreamPlayback AudioStreamPlaybackResampled
AudioStreamInteractive AudioStreamSynchronized AudioStreamPlaylist
AudioBusLayout AudioEffect AudioEffectInstance AudioEffectAmplify AudioEffectCapture
AudioEffectChorus AudioEffectCompressor AudioEffectDelay AudioEffectDistortion
AudioEffectEQ AudioEffectEQ6 AudioEffectEQ10 AudioEffectEQ21 AudioEffectFilter
AudioEffectHighPassFilter AudioEffectLowPassFilter AudioEffectLimiter
AudioEffectPitchShift AudioEffectRecord AudioEffectReverb
Material BaseMaterial3D StandardMaterial3D ORMMaterial3D ShaderMaterial
CanvasItemMaterial ParticleProcessMaterial FogMaterial PanoramaSkyMaterial
ProceduralSkyMaterial PhysicalSkyMaterial Sky Shader ShaderInclude
Mesh ArrayMesh PrimitiveMesh BoxMesh SphereMesh CylinderMesh CapsuleMesh
PlaneMesh QuadMesh PointMesh PrismMesh TorusMesh TubeTrailMesh RibbonTrailMesh
TextMesh ImmediateMesh PlaceholderMesh SurfaceTool MeshDataTool
Texture Texture2D Texture3D TextureLayered ImageTexture ImageTexture3D
ImageTextureLayered Image ImageTexture3D CompressedTexture2D CompressedTexture3D
CompressedTextureLayered CompressedCubemap CompressedCubemapArray
CompressedTexture2DArray Texture2DArray Cubemap CubemapArray GradientTexture1D
GradientTexture2D CurveTexture CurveXYZTexture AtlasTexture ViewportTexture
AnimatedTexture CameraTexture CanvasTexture NoiseTexture2D NoiseTexture3D
PlaceholderTexture2D PlaceholderTexture3D PlaceholderTextureLayered
Gradient Noise FastNoiseLite Font FontFile FontVariation SystemFont Theme
StyleBox StyleBoxEmpty StyleBoxFlat StyleBoxLine StyleBoxTexture
Shape2D Shape3D CircleShape2D RectangleShape2D CapsuleShape2D SegmentShape2D
SeparationRayShape2D WorldBoundaryShape2D ConcavePolygonShape2D ConvexPolygonShape2D
BoxShape3D SphereShape3D CapsuleShape3D CylinderShape3D HeightMapShape3D
ConcavePolygonShape3D ConvexPolygonShape3D SeparationRayShape3D WorldBoundaryShape3D
InputEvent InputEventWithModifiers InputEventFromWindow InputEventKey InputEventMouse
InputEventMouseButton InputEventMouseMotion InputEventJoypadButton
InputEventJoypadMotion InputEventAction InputEventScreenTouch InputEventScreenDrag
InputEventGesture InputEventMagnifyGesture InputEventPanGesture
TileMap TileMapLayer TileSet TileSetSource TileSetAtlasSource TileData
TileSetScenesCollectionSource TileMapPattern Polygon2D Line2D Marker2D Marker3D
ParallaxBackground ParallaxLayer Parallax2D BackBufferCopy VisibleOnScreenNotifier2D
VisibleOnScreenNotifier3D VisibleOnScreenEnabler2D VisibleOnScreenEnabler3D
HTTPRequest HTTPClient WebSocketPeer WebRTCPeerConnection WebRTCDataChannel
TCPServer StreamPeer StreamPeerTCP StreamPeerTLS StreamPeerBuffer PacketPeer
PacketPeerUDP PacketPeerDTLS DTLSServer UDPServer ENetConnection ENetPacketPeer
FileAccess DirAccess ConfigFile JSON XMLParser RegEx RegExMatch RandomNumberGenerator
Crypto CryptoKey X509Certificate HashingContext AESContext HMACContext
Mutex Semaphore Thread WorkerThreadPool ZIPReader ZIPPacker PCKPacker
ResourceFormatLoader ResourceFormatSaver PackedScene SceneState
EditorPlugin EditorScript EditorInterface EditorSettings EditorUndoRedoManager
EditorInspectorPlugin EditorProperty EditorImportPlugin EditorExportPlugin
EditorExportPlatform EditorExportPreset EditorScenePostImport EditorScenePostImportPlugin
EditorResourceConversionPlugin EditorResourcePreviewGenerator EditorNode3DGizmo
EditorNode3DGizmoPlugin EditorDebuggerPlugin EditorDebuggerSession
EditorSyntaxHighlighter SyntaxHighlighter CodeHighlighter EditorTranslationParserPlugin
EditorSceneFormatImporter EditorSceneFormatImporterFBX EditorSceneFormatImporterGLTF
EditorSceneFormatImporterBlend EditorFileDialog EditorFileSystem EditorFileSystemDirectory
EditorResourcePicker EditorScriptPicker EditorSpinSlider EditorCommandPalette
GLTFDocument GLTFState GLTFDocumentExtension GLTFNode GLTFMesh GLTFBufferView
GLTFAnimation GLTFTexture GLTFMaterial GLTFPhysicsBody GLTFPhysicsShape
RenderingDevice RenderingServer DisplayServer AudioServer PhysicsServer2D
PhysicsServer3D PhysicsDirectBodyState2D PhysicsDirectBodyState3D
PhysicsDirectSpaceState2D PhysicsDirectSpaceState3D PhysicsRayQueryParameters2D
PhysicsRayQueryParameters3D PhysicsShapeQueryParameters2D PhysicsShapeQueryParameters3D
PhysicsPointQueryParameters2D PhysicsPointQueryParameters3D
PhysicsTestMotionParameters2D PhysicsTestMotionParameters3D PhysicsTestMotionResult2D
PhysicsTestMotionResult3D GDExtension ScriptExtension
""".split())

# Script resources themselves expose Resource/Object APIs. Recognizing these
# avoids treating Foo.new(), Foo.get_script_method_list(), etc. as script funcs.
SCRIPT_METHODS = frozenset("""
new can_instantiate instance_has get_base_script get_global_name
get_instance_base_type has_source_code get_source_code set_source_code reload
get_script_property_list get_script_method_list get_script_signal_list
get_script_constant_map get_property_default_value is_tool get_rpc_config
get_as_text get_dependencies get_local_scene setup_local_to_scene is_built_in
take_over_path emit_changed duplicate duplicate_deep reset_state
set_path_cache get_rid get_id_for_path set_id_for_path generate_scene_unique_id
get_meta set_meta has_meta remove_meta get_meta_list get_class is_class
get_instance_id set get set_indexed get_indexed get_property_list
get_method_list get_signal_list has_method has_signal get_signal_connection_list
get_incoming_connections add_user_signal remove_user_signal emit_signal
connect disconnect is_connected set_block_signals is_blocking_signals
call callv call_deferred set_deferred notification notify_property_list_changed
free cancel_free is_queued_for_deletion to_string tr tr_n
""".split())


@dataclass
class FunctionScope:
    first_line: int
    last_line: int
    shadows: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class ScriptInfo:
    source: Source
    methods: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)
    names: set[str] = field(default_factory=set)
    class_name: str | None = None
    parent: list[Token] = field(default_factory=list)
    inner_ranges: list[tuple[int, int]] = field(default_factory=list)
    scopes: list[FunctionScope] = field(default_factory=list)
    class_scopes: list[tuple[str, int, int]] = field(default_factory=list)


def _logical_lines(tokens: list[Token]) -> list[list[Token]]:
    """Keep multiline literals, annotations and argument lists together."""
    result: list[list[Token]] = []
    current: list[Token] = []
    depth = 0
    for token in tokens:
        if token.kind == "NEWLINE":
            if depth == 0 and not (current and current[-1].value == "\\"):
                if current:
                    result.append(current)
                    current = []
            elif current and current[-1].value == "\\":
                current.pop()
            continue
        if token.kind == "SYMBOL" and token.value == ";" and depth == 0 and current:
            start = _declaration_start(current)
            if (start < len(current) and current[start].kind == "IDENT"
                    and current[start].value in {"var", "const", "signal", "extends", "class_name"}
                    and not any(part.kind == "IDENT" and part.value == "func" for part in current)):
                result.append(current)
                current = []
                continue
        current.append(token)
        if token.kind == "SYMBOL":
            if token.value in "([{":
                depth += 1
            elif token.value in ")]}":
                depth = max(0, depth - 1)
    if current:
        result.append(current)
    return result


def _declaration_start(tokens: list[Token]) -> int:
    """Skip declaration modifiers and same-line @annotations."""
    index = 0
    while index < len(tokens):
        if tokens[index].kind == "IDENT" and tokens[index].value in {"static", "abstract"}:
            index += 1
        elif tokens[index].kind == "SYMBOL" and tokens[index].value == "@" and index + 1 < len(tokens):
            index += 2
            if index < len(tokens) and tokens[index].value == "(":
                _, end = arguments(tokens, index)
                index = end + 1
        else:
            break
    return index


def _resource_path(source: Source, value: str) -> str | None:
    if value.startswith("res://"):
        path = value[6:]
    elif "://" in value or value.startswith(("/", "\\")):
        return None
    else:
        path = posixpath.join(posixpath.dirname(source.relative), value)
    path = posixpath.normpath(path.replace("\\", "/"))
    return None if path == ".." or path.startswith("../") else path


def _preload_alias(tokens: list[Token], source: Source) -> str | None:
    # Only a literal preload initializer denotes a known script alias. In
    # particular, preload(...).new() is an instance, not a script class.
    equal = next((i for i, t in enumerate(tokens) if t.value in {"=", ":="}), -1)
    if equal < 0:
        return None
    value = tokens[equal + 1:]
    while len(value) >= 2 and value[0].value == "(" and value[-1].value == ")":
        _, end = arguments(value, 0)
        if end != len(value) - 1:
            break
        value = value[1:-1]
    if len(value) != 4 or value[0].kind != "IDENT" or value[0].value != "preload" or value[1].value != "(" or value[2].kind != "STRING" or value[3].value != ")":
        return None
    return _resource_path(source, value[2].value)


def _script_file_exists(ctx: Context, source: Source, value: str) -> bool:
    relative = _resource_path(source, value)
    if relative is not None:
        return relative in ctx.files
    # The rule checks existence in the checkout. A sibling file referenced by
    # a tool script must not be labelled missing merely because it is outside
    # game/. Its declarations are outside this project's method index.
    resource = value if value.startswith("res://") else "res://" + posixpath.join(
        posixpath.dirname(source.relative), value)
    if not ctx.exists(resource):
        return False
    return (ctx.root / resource[6:]).is_file()


def _inspect_script(ctx: Context, source: Source) -> ScriptInfo:
    info = ScriptInfo(source)
    lines = _logical_lines(source.tokens)
    class_blocks: list[tuple[str, int, int, int]] = []
    for index, row in enumerate(lines):
        offset = _declaration_start(row)
        if offset + 1 >= len(row) or row[offset].kind != "IDENT" or row[offset].value != "class":
            continue
        declaration, name = row[offset:offset + 2]
        if name.kind != "IDENT":
            continue
        end = next((following[0].line - 1 for following in lines[index + 1:]
                    if following[0].line > declaration.line and following[0].column <= row[0].column),
                   source.text.count("\n") + 1)
        class_blocks.append((name.value, declaration.line, end, row[0].column))
    for name, first, last, indent in class_blocks:
        parents = [block for block in class_blocks if block[1] < first <= block[2] and block[3] < indent]
        parent = max(parents, key=lambda block: block[3]) if parents else None
        info.class_scopes.append((name, parent[1] if parent else 1,
                                 parent[2] if parent else source.text.count("\n") + 1))
    top_line_numbers = {row[0].line for row in lines if row[0].column == 0}
    top = [(i, row) for i, row in enumerate(lines) if row[0].line in top_line_numbers]
    declarations: dict[str, Token] = {}
    for position, (row_index, row) in enumerate(top):
        offset = _declaration_start(row)
        if offset + 1 >= len(row):
            continue
        kind, name = row[offset], row[offset + 1]
        if kind.kind != "IDENT":
            continue
        last_line = (top[position + 1][1][0].line - 1) if position + 1 < len(top) else source.text.count("\n") + 1
        if kind.value == "class_name" and name.kind == "IDENT":
            info.class_name = name.value
        if kind.value == "extends":
            info.parent = row[offset + 1:]
        elif kind.value == "class_name":
            for index, token in enumerate(row):
                if token.value == "extends":
                    info.parent = row[index + 1:]
                    break
        if kind.value == "class":
            info.inner_ranges.append((kind.line, last_line))
            info.names.add(name.value)
        if kind.value not in {"func", "signal", "var", "const"} or name.kind != "IDENT":
            continue
        if name.value in declarations:
            first = declarations[name.value]
            ctx.emit("blocker", "duplicate-declaration", source, name.line,
                     f"최상위 이름 '{name.value}' 중복 선언 (첫 선언: {first.line}행)")
        else:
            declarations[name.value] = name
        info.names.add(name.value)
        if kind.value == "const":
            alias = _preload_alias(row[offset:], source)
            if alias is not None:
                info.aliases[name.value] = alias
        if kind.value != "func":
            continue
        info.methods.add(name.value)
        scope = FunctionScope(kind.line, last_line)
        inline_body: list[Token] = []
        if offset + 2 < len(row) and row[offset + 2].value == "(":
            params, end = arguments(row, offset + 2)
            scope.shadows.update(part[0].value for part in params if part and part[0].kind == "IDENT")
            inline_body = row[end + 1:]
        for body_row in ([inline_body] if inline_body else []) + lines[row_index + 1:]:
            if body_row[0].line > last_line:
                break
            for index, token in enumerate(body_row[:-1]):
                if token.kind == "IDENT" and token.value in {"var", "const", "for"} and body_row[index + 1].kind == "IDENT":
                    local_name = body_row[index + 1].value
                    scope.shadows.add(local_name)
                    if token.value == "const":
                        alias = _preload_alias(body_row[index:], source)
                        if alias is not None:
                            scope.aliases[local_name] = alias
                if token.kind == "IDENT" and token.value == "func" and body_row[index + 1].value == "(":
                    params, _ = arguments(body_row, index + 1)
                    scope.shadows.update(part[0].value for part in params if part and part[0].kind == "IDENT")
        info.scopes.append(scope)
    return info


def _parent_target(info: ScriptInfo, classes: dict[str, ScriptInfo], scripts: dict[str, ScriptInfo]) -> ScriptInfo | str | None:
    if not info.parent:
        return "RefCounted"
    token = info.parent[0]
    # An explicitly selected inner class requires a full class-scope parser;
    # leave its inherited API unresolved instead of emitting false blockers.
    if len(info.parent) > 1 and info.parent[1].value == ".":
        return None
    if token.kind == "STRING":
        return scripts.get(_resource_path(info.source, token.value) or "")
    if token.value in classes:
        return classes[token.value]
    if token.value in info.aliases:
        return scripts.get(info.aliases[token.value])
    return token.value if token.value in NATIVE_CLASSES else None


def _has_method(info: ScriptInfo, method: str, classes: dict[str, ScriptInfo], scripts: dict[str, ScriptInfo], seen: set[str] | None = None) -> bool | None:
    if method in info.methods or method in SCRIPT_METHODS:
        return True
    seen = set() if seen is None else seen
    if info.source.relative in seen:
        return None
    seen.add(info.source.relative)
    parent = _parent_target(info, classes, scripts)
    if isinstance(parent, ScriptInfo):
        return _has_method(parent, method, classes, scripts, seen)
    if parent is None:
        return None
    # Custom script static functions are discoverable; native static APIs are
    # not. RefCounted/Object/Node bases have no additional relevant static API.
    if parent not in {"Object", "RefCounted", "Node", "Node2D", "Node3D", "SceneTree", "Control", "CanvasLayer"}:
        return None
    return False


def check_scripts(ctx: Context) -> None:
    """Emit duplicate-declaration, missing-preload/extends/method blockers."""
    scripts = {path: _inspect_script(ctx, source) for path, source in ctx.sources.items() if path.endswith(".gd")}
    class_lists: dict[str, list[ScriptInfo]] = {}
    for info in scripts.values():
        if info.class_name:
            class_lists.setdefault(info.class_name, []).append(info)
    classes = {name: entries[0] for name, entries in class_lists.items() if len(entries) == 1}
    for info in scripts.values():
        tokens = significant(info.source.tokens)
        for index, token in enumerate(tokens):
            if token.kind != "IDENT":
                continue
            if token.value == "preload" and index + 1 < len(tokens) and tokens[index + 1].value == "(":
                args, _ = arguments(tokens, index + 1)
                if len(args) == 1 and len(args[0]) == 1 and args[0][0].kind == "STRING":
                    value = args[0][0]
                    path = _resource_path(info.source, value.value)
                    if value.value.startswith("uid://"):
                        ctx.emit("warning", "unresolved-preload", info.source, value.line,
                                 f"UID preload 스크립트 해석 생략: {value.value}")
                    elif not _script_file_exists(ctx, info.source, value.value):
                        ctx.emit("blocker", "missing-preload", info.source, value.line,
                                 f"preload 파일 없음: {value.value}",
                                 resource="res://" + path if path is not None else value.value)
            if token.value == "extends" and index + 1 < len(tokens):
                target = tokens[index + 1]
                if target.kind == "STRING":
                    path = _resource_path(info.source, target.value)
                    if target.value.startswith("uid://"):
                        ctx.emit("warning", "unresolved-extends", info.source, target.line,
                                 f"UID extends 스크립트 해석 생략: {target.value}")
                    elif not _script_file_exists(ctx, info.source, target.value):
                        ctx.emit("blocker", "missing-extends", info.source, target.line,
                                 f"extends 스크립트 없음: {target.value}")
                elif (target.kind == "IDENT" and target.value not in NATIVE_CLASSES
                      and target.value not in class_lists and target.value not in info.aliases
                      and not any(name == target.value and first <= token.line <= last
                                  for name, first, last in info.class_scopes)):
                    ctx.emit("blocker", "missing-extends", info.source, target.line,
                             f"extends 클래스 정의 없음: {target.value}")
            if index + 3 >= len(tokens) or tokens[index + 1].value != "." or tokens[index + 2].kind != "IDENT" or tokens[index + 3].value != "(":
                continue
            if index and tokens[index - 1].value in {".", "$", "%"}:
                continue
            if any(first <= token.line <= last for first, last in info.inner_ranges):
                continue
            scope = next((scope for scope in info.scopes if scope.first_line <= token.line <= scope.last_line), None)
            if scope and token.value in scope.aliases:
                target_info = scripts.get(scope.aliases[token.value])
            elif scope and token.value in scope.shadows:
                continue
            elif token.value in info.aliases:
                target_info = scripts.get(info.aliases[token.value])
            elif token.value in info.names:
                continue
            else:
                target_info = classes.get(token.value)
            if target_info is None:
                continue
            method = tokens[index + 2]
            if _has_method(target_info, method.value, classes, scripts) is False:
                ctx.emit("blocker", "missing-method", info.source, token.line,
                         f"{token.value}.{method.value}(): {target_info.source.relative} 및 확인 가능한 부모에 메서드 없음")
